// Baseline "naive" N-of-N multi-signature issuer node, used as a second
// point of comparison (alongside the single-issuer baseline in
// issuer_baseline.py) against the FROST threshold-signature scheme
// implemented in ../main.go.
//
// Unlike the FROST node, this node does NOT run any distributed
// key-generation protocol and does NOT talk to its peers at all: each
// node independently generates its own long-term Ed25519 keypair at
// startup and, on request, signs the message with that key alone. A VC
// under this scheme carries N independent (pubkey, signature) pairs
// instead of a single constant-size aggregate signature, and the
// verifier must check all N of them individually. This mirrors the
// "collect one signature from each of the N issuers" pattern used by the
// competing decentralized-authentication schemes cited in the paper,
// which do not employ threshold cryptography.
//
// Because no peer-to-peer coordination round exists, the orchestrator
// only needs a single request/response with each node (no keygen phase
// to poll for), which is the point this baseline is meant to quantify:
// how much of FROST's latency is actually the cost of the DKG + signing
// rounds, versus the unavoidable cost of reaching N remote issuers over
// a network with latency L.
package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"sync"
)

type Node struct {
	Id       int
	pub      ed25519.PublicKey
	priv     ed25519.PrivateKey
	mu       sync.Mutex
	signature []byte
}

func NewNode(id int) *Node {
	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		log.Fatalf("key generation failed: %v", err)
	}
	return &Node{Id: id, pub: pub, priv: priv}
}

func (nd *Node) adminStartSignHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Message string `json:"message"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	go func() {
		sig := ed25519.Sign(nd.priv, []byte(req.Message))
		nd.mu.Lock()
		nd.signature = sig
		nd.mu.Unlock()
	}()
	w.WriteHeader(http.StatusAccepted)
}

func (nd *Node) statusHandler(w http.ResponseWriter, r *http.Request) {
	type statusT struct {
		ID              int    `json:"id"`
		KeygenDone      bool   `json:"keygen_done"`
		PublicKeyBase64 string `json:"public_key_base64"`
		SignatureBase64 string `json:"signature_base64,omitempty"`
	}
	nd.mu.Lock()
	sig := nd.signature
	nd.mu.Unlock()

	st := statusT{
		ID:              nd.Id,
		KeygenDone:      true, // no DKG round exists in this scheme
		PublicKeyBase64: base64.StdEncoding.EncodeToString(nd.pub),
	}
	if sig != nil {
		st.SignatureBase64 = base64.StdEncoding.EncodeToString(sig)
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(st)
}

func main() {
	id := flag.Int("id", 1, "node id (1-based)")
	basePort := flag.Int("base-port", 8000, "base port: node i listens on base-port + (i-1)")
	flag.Parse()

	node := NewNode(*id)

	mux := http.NewServeMux()
	mux.HandleFunc("/admin/start-sign", node.adminStartSignHandler)
	mux.HandleFunc("/status", node.statusHandler)

	addr := fmt.Sprintf("0.0.0.0:%d", *basePort+*id-1)
	log.Printf("[multisig node %d] starting HTTP server on %s", *id, addr)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatalf("server failed: %v", err)
	}
}
