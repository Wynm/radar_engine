import argparse
import json
import sys
from datetime import datetime


class DATMetadataEngine:
    """
    Cardano Distributed Asset Tokens (DAT) Metadata Engine.
    Validates and generates metadata JSON schemas for Cardano tokens.
    """

    REQUIRED_FIELDS = ["name", "image", "mediaType"]

    def __init__(self):
        pass

    def validate_metadata(self, metadata: dict) -> dict:
        """
        Validates token metadata against Cardano DAT / CIP-25 standards.
        Returns validation status, compliance score, errors, and warnings.
        """
        errors = []
        warnings = []
        score = 100

        if not isinstance(metadata, dict):
            return {
                "valid": False,
                "score": 0,
                "errors": ["Metadata input must be a JSON object."],
                "warnings": [],
            }

        # Check root standard structure (CIP-25 / DAT format)
        root_key = "721" if "721" in metadata else ("dat_standard" if "dat_standard" in metadata else None)
        target_data = metadata.get(root_key, metadata) if root_key else metadata

        if not root_key:
            warnings.append("Root standard key ('721' or 'dat_standard') missing. Assuming payload contains token attributes directly.")
            score -= 10

        token_entries = []

        if isinstance(target_data, dict):
            for policy_id, policy_contents in target_data.items():
                if policy_id in ("version", "mediaType"):
                    continue
                if isinstance(policy_contents, dict):
                    for asset_name, asset_meta in policy_contents.items():
                        if isinstance(asset_meta, dict):
                            token_entries.append((asset_name, asset_meta))
                        else:
                            token_entries.append((policy_id, policy_contents))
                            break

        if not token_entries and isinstance(metadata, dict):
            token_entries = [("direct_asset", metadata)]

        for asset_name, asset_data in token_entries:
            if not isinstance(asset_data, dict):
                errors.append(f"Asset payload for '{asset_name}' must be a JSON object.")
                score -= 30
                continue

            for field in self.REQUIRED_FIELDS:
                if field not in asset_data:
                    errors.append(f"Missing required field '{field}' in asset '{asset_name}'.")
                    score -= 25
                elif not asset_data[field]:
                    warnings.append(f"Required field '{field}' in asset '{asset_name}' is empty.")
                    score -= 10

            # URI protocol verification
            image_uri = asset_data.get("image", "")
            if isinstance(image_uri, str) and image_uri:
                valid_prefixes = ("ipfs://", "https://", "ar://")
                if not any(image_uri.startswith(p) for p in valid_prefixes):
                    warnings.append(f"Image URI for '{asset_name}' should use ipfs://, ar://, or https:// protocols.")
                    score -= 10

        score = max(0, score)
        return {
            "valid": len(errors) == 0,
            "score": score,
            "errors": errors,
            "warnings": warnings,
            "validated_at": datetime.utcnow().isoformat() + "Z"
        }

    def generate_metadata(self, policy_id: str, asset_name: str, display_name: str, image_uri: str, media_type: str = "image/png", attributes: dict = None) -> dict:
        """
        Generates a valid Cardano DAT / CIP-25 compliant metadata structure.
        """
        return {
            "721": {
                policy_id: {
                    asset_name: {
                        "name": display_name,
                        "image": image_uri,
                        "mediaType": media_type,
                        "files": [
                            {
                                "name": display_name,
                                "mediaType": media_type,
                                "src": image_uri
                            }
                        ],
                        "attributes": attributes or {}
                    }
                },
                "version": "1.0"
            }
        }


def run_self_test() -> int:
    """Executes self-test suite for the engine without touching external system files."""
    print("=== RUNNING SELF-TEST: Cardano DAT Metadata Standard Engine ===")
    engine = DATMetadataEngine()

    # 1. Test Metadata Generation
    dummy_policy = "00000000000000000000000000000000000000000000000000000000"
    generated = engine.generate_metadata(
        policy_id=dummy_policy,
        asset_name="TestToken01",
        display_name="Golden Opportunity Token",
        image_uri="ipfs://QmTest123456789Hash",
        attributes={"rarity": "Legendary", "utility": "Access Pass"}
    )
    assert "721" in generated, "FAIL: Metadata generation missing '721' root key."
    print("[PASS] Metadata Generation Test")

    # 2. Test Validation on Valid Payload
    val_valid = engine.validate_metadata(generated)
    assert val_valid["valid"] is True, f"FAIL: Expected valid payload, got errors: {val_valid['errors']}"
    assert val_valid["score"] == 100, f"FAIL: Score should be 100, got {val_valid['score']}"
    print("[PASS] Valid Metadata Validation Test (Compliance Score: 100%)")

    # 3. Test Validation on Invalid Payload
    invalid_payload = {"name": "IncompleteToken"}  # Missing image and mediaType
    val_invalid = engine.validate_metadata(invalid_payload)
    assert val_invalid["valid"] is False, "FAIL: Invalid metadata was incorrectly marked as valid."
    assert len(val_invalid["errors"]) >= 2, "FAIL: Validation failed to detect missing required fields."
    print("[PASS] Invalid Metadata Detection Test")

    print("\n--- ALL SELF-TESTS PASSED SUCCESSFULLY ---")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Cardano DAT Metadata Validator & Generator Micro-SaaS Engine")
    parser.add_argument("--self-test", action="store_true", help="Execute self-test suite and print result.")
    parser.add_argument("--validate", type=str, help="JSON string or file path to validate metadata.")

    args = parser.parse_args()

    if args.self_test:
        sys.exit(run_self_test())

    if args.validate:
        engine = DATMetadataEngine()
        try:
            data = json.loads(args.validate)
        except json.JSONDecodeError:
            try:
                with open(args.validate, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(json.dumps({"error": f"Failed to parse JSON: {str(e)}"}))
                sys.exit(1)

        report = engine.validate_metadata(data)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
