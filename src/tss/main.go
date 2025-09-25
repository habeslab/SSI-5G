package main

import (
    "encoding/base64"
    "encoding/json"
    "flag"
    "fmt"
    "log"
    "net/http"
    "os"
    "strconv"
    "sync"
    "time"

    "github.com/gorilla/websocket"

    "github.com/taurusgroup/frost-ed25519/pkg/frost"
    "github.com/taurusgroup/frost-ed25519/pkg/frost/keygen"
    "github.com/taurusgroup/frost-ed25519/pkg/frost/party"
    "github.com/taurusgroup/frost-ed25519/pkg/frost/sign"
    "github.com/taurusgroup/frost-ed25519/pkg/messages"
    "github.com/taurusgroup/frost-ed25519/pkg/state"
    "github.com/taurusgroup/frost-ed25519/pkg/eddsa"
    "crypto/ed25519"
)

var upgrader = websocket.Upgrader{CheckOrigin: func(r *http.Request) bool { return true }}

type Node struct {
    Id        party.ID
    N         int
    Threshold party.Size
    BasePort  int

    peers   map[party.ID]*websocket.Conn
    peersMu sync.RWMutex

    recv chan []byte
    send chan *messages.Message

    keygenOutput *keygen.Output
    signOutput   *sign.Output
}

func NewNode(id int, n int, basePort int, threshold int) *Node {
    return &Node{
        Id:        party.ID(id),
        N:         n,
        Threshold: party.Size(threshold),
        BasePort:  basePort,
        peers:     make(map[party.ID]*websocket.Conn),
        recv:      make(chan []byte, 1024),
        send:      make(chan *messages.Message, 1024),
    }
}

func (nd *Node) waitForAllPeers() {
    for {
        nd.peersMu.RLock()
        count := len(nd.peers)
        nd.peersMu.RUnlock()
        if count == nd.N-1 {
            return
        }
        time.Sleep(100 * time.Millisecond)
    }
}

func (nd *Node) Start() {
    mux := http.NewServeMux()
    mux.HandleFunc("/ws", nd.wsHandler)
    mux.HandleFunc("/admin/start-sign", nd.adminStartSignHandler)
    mux.HandleFunc("/status", nd.statusHandler)

    addr := fmt.Sprintf("127.0.0.1:%d", nd.BasePort+int(nd.Id)-1)
    srv := &http.Server{Addr: addr, Handler: mux}

    go func() {
        log.Printf("[node %d] starting HTTP+WS server on %s", nd.Id, addr)
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            log.Fatalf("server failed: %v", err)
        }
    }()

    time.Sleep(200 * time.Millisecond)

    for pid := int(nd.Id) + 1; pid <= nd.N; pid++ {
        go nd.dialPeer(party.ID(pid))
    }

    nd.waitForAllPeers()
    go nd.sendPump()

    ids := make([]party.ID, nd.N)
    for i := 1; i <= nd.N; i++ {
        ids[i-1] = party.ID(i)
    }
    set := party.NewIDSlice(ids)

    go nd.runKeyGen(set, nd.Threshold)
}

func (nd *Node) wsHandler(w http.ResponseWriter, r *http.Request) {
    conn, err := upgrader.Upgrade(w, r, nil)
    if err != nil {
        log.Println("upgrade error:", err)
        return
    }

    remoteStr := r.URL.Query().Get("id")
    remoteInt, _ := strconv.Atoi(remoteStr)
    remote := party.ID(remoteInt)
    if remote == nd.Id {
        conn.Close()
        return
    }

    nd.peersMu.Lock()
    if old, ok := nd.peers[remote]; ok {
        old.Close()
    }
    nd.peers[remote] = conn
    nd.peersMu.Unlock()

    log.Printf("[node %d] accepted connection from %d", nd.Id, remote)
    go nd.connReadLoop(conn, remote)
}

func (nd *Node) dialPeer(remote party.ID) {
    url := fmt.Sprintf("ws://127.0.0.1:%d/ws?id=%d", nd.BasePort+int(remote)-1, int(nd.Id))
    for {
        conn, _, err := websocket.DefaultDialer.Dial(url, nil)
        if err != nil {
            time.Sleep(300 * time.Millisecond)
            continue
        }
        nd.peersMu.Lock()
        if old, ok := nd.peers[remote]; ok {
            old.Close()
        }
        nd.peers[remote] = conn
        nd.peersMu.Unlock()
        log.Printf("[node %d] connected to peer %d", nd.Id, remote)
        go nd.connReadLoop(conn, remote)
        return
    }
}

func (nd *Node) connReadLoop(conn *websocket.Conn, remote party.ID) {
    defer func() {
        conn.Close()
        nd.peersMu.Lock()
        if nd.peers[remote] == conn {
            delete(nd.peers, remote)
        }
        nd.peersMu.Unlock()
    }()

    for {
        mt, data, err := conn.ReadMessage()
        if err != nil {
            log.Printf("[node %d] read error from %d: %v", nd.Id, remote, err)
            return
        }
        if mt != websocket.BinaryMessage {
            continue
        }
        nd.recv <- data
    }
}

func (nd *Node) sendPump() {
    for msg := range nd.send {
        data, err := msg.MarshalBinary()
        if err != nil {
            log.Println("marshal error:", err)
            continue
        }
        if msg.IsBroadcast() {
            nd.peersMu.RLock()
            for pid, conn := range nd.peers {
                if pid == msg.From {
                    continue
                }
                _ = conn.WriteMessage(websocket.BinaryMessage, data)
            }
            nd.peersMu.RUnlock()
        } else {
            nd.peersMu.RLock()
            conn := nd.peers[msg.To]
            nd.peersMu.RUnlock()
            if conn == nil {
                log.Printf("[node %d] no connection to %d", nd.Id, msg.To)
                continue
            }
            _ = conn.WriteMessage(websocket.BinaryMessage, data)
        }
    }
}

func (nd *Node) handleState(s *state.State) {
    for {
        select {
        case data := <-nd.recv:
            var msg messages.Message
            if err := msg.UnmarshalBinary(data); err != nil {
                log.Println("unmarshal error:", err)
                continue
            }
            if err := s.HandleMessage(&msg); err != nil {
                log.Println("failed to handle message:", err)
                continue
            }
            for _, mo := range s.ProcessAll() {
                nd.send <- mo
            }
        case <-s.Done():
            if err := s.WaitForError(); err != nil {
                log.Printf("[node %d] protocol aborted: %v", nd.Id, err)
            }
            return
        }
    }
}

func (nd *Node) runKeyGen(set party.IDSlice, threshold party.Size) {
    keygenState, keygenOutput, err := frost.NewKeygenState(nd.Id, set, threshold, 20*time.Second)
    if err != nil {
        log.Fatalf("NewKeygenState: %v", err)
    }

    go nd.handleState(keygenState)

    initial := keygenState.ProcessAll()
    for _, m := range initial {
        nd.send <- m
    }

    if err := keygenState.WaitForError(); err != nil {
        log.Printf("[node %d] keygen aborted: %v", nd.Id, err)
        return
    }

    nd.keygenOutput = keygenOutput
    _, byteData, keyBase64 := printGroupKey(keygenOutput.Public.GroupKey)
    log.Printf("[node %d] GroupKey serialized (raw): %x", nd.Id, byteData)
    log.Printf("[node %d] GroupKey serialized (Base64): %s", nd.Id, keyBase64)
}

func (nd *Node) runSign(signers []party.ID, message []byte) {
    if nd.keygenOutput == nil {
        log.Printf("[node %d] no keygen output available, cannot sign", nd.Id)
        return
    }
    ids := make([]party.ID, len(signers))
    copy(ids, signers)
    signersSlice := party.NewIDSlice(ids)

    secretShare := nd.keygenOutput.SecretKey
    public := nd.keygenOutput.Public

    signState, signOutput, err := frost.NewSignState(signersSlice, secretShare, public, message, 20*time.Second)
    if err != nil {
        log.Fatalf("NewSignState: %v", err)
    }

    go nd.handleState(signState)

    for _, m := range signState.ProcessAll() {
        nd.send <- m
    }

    if err := signState.WaitForError(); err != nil {
        log.Printf("[node %d] sign aborted: %v", nd.Id, err)
    }

    nd.signOutput = signOutput

    // Firma Ed25519 standard
    sigEd := signOutput.Signature.ToEd25519()
    sigB64 := base64.StdEncoding.EncodeToString(sigEd)
    log.Printf("[node %d] Signature generated (Ed25519, Base64): %s", nd.Id, sigB64)

    if nd.Id == 1 {
        _, _, groupKeyB64 := printGroupKey(nd.keygenOutput.Public.GroupKey)
        writeIssuerOutput(groupKeyB64, message, sigB64)
    }
}

func (nd *Node) adminStartSignHandler(w http.ResponseWriter, r *http.Request) {
    var req struct {
        Signers []int  `json:"signers"`
        Message string `json:"message"`
    }
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, "bad request", http.StatusBadRequest)
        return
    }
    signerIDs := make([]party.ID, 0, len(req.Signers))
    myIn := false
    for _, s := range req.Signers {
        pid := party.ID(s)
        signerIDs = append(signerIDs, pid)
        if pid == nd.Id {
            myIn = true
        }
    }
    if myIn {
        go nd.runSign(signerIDs, []byte(req.Message))
    }
    w.WriteHeader(http.StatusAccepted)
}

func (nd *Node) statusHandler(w http.ResponseWriter, r *http.Request) {
    type statusT struct {
        ID              int    `json:"id"`
        KeygenDone      bool   `json:"keygen_done"`
        GroupKeyBase64  string `json:"group_key_base64,omitempty"`
        SignatureBase64 string `json:"signature_base64,omitempty"`
    }
    st := statusT{ID: int(nd.Id)}
    if nd.keygenOutput != nil {
        _, _, b64 := printGroupKey(nd.keygenOutput.Public.GroupKey)
        st.KeygenDone = true
        st.GroupKeyBase64 = b64
    }
    if nd.signOutput != nil {
        s := nd.signOutput.Signature.ToEd25519()
        st.SignatureBase64 = base64.StdEncoding.EncodeToString(s)
    }
    w.Header().Set("Content-Type", "application/json")
    _ = json.NewEncoder(w).Encode(st)
}

func printGroupKey(key *eddsa.PublicKey) (string, ed25519.PublicKey, string) {
    byteData := key.ToEd25519()
    hexString := fmt.Sprintf("%x", byteData)
    keyBase64 := base64.StdEncoding.EncodeToString(byteData)
    return hexString, byteData, keyBase64
}

// Genera issuer_output.json con messaggio leggibile e firma Ed25519 standard
func writeIssuerOutput(groupKeyB64 string, message []byte, signatureB64 string) {
    output := map[string]interface{}{
        "sign_issuer_pubkey": groupKeyB64,
        "verifiable_cred": map[string]interface{}{
            "attr":       string(message), // messaggio leggibile
            "issuer_sig": signatureB64,    // firma Ed25519 standard
        },
    }

    file, err := os.Create("issuer_output.json")
    if err != nil {
        log.Printf("failed to create issuer_output.json: %v", err)
        return
    }
    defer file.Close()

    enc := json.NewEncoder(file)
    enc.SetIndent("", "    ")
    if err := enc.Encode(output); err != nil {
        log.Printf("failed to write JSON: %v", err)
    } else {
        log.Println("issuer_output.json generated successfully")
    }
}

func main() {
    id := flag.Int("id", 1, "node id (1-based)")
    n := flag.Int("n", 3, "total number of nodes")
    basePort := flag.Int("base-port", 8000, "base port: node i listens on base-port + (i-1)")
    threshold := flag.Int("threshold", 2, "threshold size")
    flag.Parse()

    node := NewNode(*id, *n, *basePort, *threshold)
    node.Start()

    select {}
}