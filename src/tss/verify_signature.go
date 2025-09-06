package main

import (
	"crypto/ed25519"
	"fmt"
	"log"

	"github.com/mr-tron/base58"
)

func main() {
	// Hardcoded input in Base58
	message := []byte("ciao mario")
	pubB58 := "5BEuDPJRP7QKt5CaarAUk1PyP5xo6k2GSpyar7KzNdA8"
	sigB58 := "3dZ6sA7wQnAXmataR45x2aBt7J6Av19hrhM7bxh7uJQMH3WdpgXqTSrHyrgVuS9EGZ16XMY7X756rm9K6vnErr8w"

	// Decodifica chiave pubblica Base58
	pubBytes, err := base58.Decode(pubB58)
	if err != nil {
		log.Fatalf("Errore decodifica chiave pubblica Base58: %v", err)
	}
	pubKey := ed25519.PublicKey(pubBytes)

	// Decodifica firma Base58
	sigBytes, err := base58.Decode(sigB58)
	if err != nil {
		log.Fatalf("Errore decodifica firma Base58: %v", err)
	}

	// Verifica firma
	if ed25519.Verify(pubKey, message, sigBytes) {
		fmt.Println("✅ Firma valida!")
	} else {
		fmt.Println("❌ Firma non valida!")
	}
}
