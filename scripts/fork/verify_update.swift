import Foundation
import CryptoKit

let arguments = CommandLine.arguments
guard arguments.count == 4,
      let publicKeyData = Data(base64Encoded: arguments[1]),
      let signature = Data(base64Encoded: arguments[2]) else { fatalError("Expected public key, signature, and archive path") }
let publicKey = try Curve25519.Signing.PublicKey(rawRepresentation: publicKeyData)
let archive = try Data(contentsOf: URL(fileURLWithPath: arguments[3]), options: .mappedIfSafe)
guard publicKey.isValidSignature(signature, for: archive) else { fatalError("Update signature does not match the app's public key") }
print("Update archive signature verified")
