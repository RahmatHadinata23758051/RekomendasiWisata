#!/usr/bin/env python3
"""CLI driver for the secure Apify Google Maps batch runner."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path if running as standalone script
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.apify_runner import ApifyBatchRunner, ApifyRunnerError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Terminal Apify Batch Runner: secure execution of versioned Apify Google Maps batches",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "--list-batches",
        action="store_true",
        help="List all versioned batches and files from the authoritative index",
    )
    action_group.add_argument(
        "--verify-token",
        action="store_true",
        help="Verify APIFY_TOKEN against the Apify REST API without starting any runs",
    )
    action_group.add_argument(
        "--batch",
        type=str,
        help="Execute or plan all files in the given batch (e.g. batch-01-canary)",
    )
    action_group.add_argument(
        "--file",
        type=str,
        help="Execute or plan a single batch JSON file (relative to batches root or index path)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate JSON files and print planned runs without spending real API credits or contacting Apify",
    )
    parser.add_argument(
        "--no-import",
        action="store_true",
        help="Skip auto-invoking ApifyGoogleMapsImporter after download",
    )
    parser.add_argument(
        "--batches-root",
        type=str,
        default="config/apify_batches",
        help="Root directory containing index.csv and versioned batches",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default="data/raw/apify/google_maps",
        help="Root directory for downloaded raw places.json artifacts",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Fail instead of prompting interactively if APIFY_TOKEN is unset",
    )
    token_group = parser.add_argument_group("Token options")
    token_group.add_argument(
        "--token-file",
        type=str,
        metavar="PATH",
        help="Path to a file containing one APIFY_TOKEN per line (e.g. .apify-tokens)",
    )
    token_group.add_argument(
        "--token-index",
        type=int,
        default=0,
        metavar="N",
        help="0-based index of the token to use from --token-file",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    runner = ApifyBatchRunner(
        batches_root=args.batches_root,
        output_root=args.output_root,
    )

    try:
        if args.list_batches:
            batches = runner.list_batches()
            print(f"Authoritative index contains {len(batches)} file(s):")
            for b in batches:
                print(f"  [{b.batch}] {b.file} -> {b.region_id} ({b.kind})")
            return 0

        if args.verify_token:
            token = runner.token_from_environment_or_prompt(
                prompt=not args.no_prompt,
                token_file=args.token_file,
                token_index=args.token_index,
            )
            print("Verifying token with Apify REST API...")
            info = runner.verify_token(token)
            username = info.get("username") or info.get("id") or "verified"
            email = info.get("email", "")
            print(f"Token verified successfully. User: {username} {f'({email})' if email else ''}")
            return 0

        if not args.batch and not args.file:
            parser.print_help()
            return 1

        targets = runner.targets(batch=args.batch, file=args.file)

        if args.dry_run:
            planned = runner.dry_run(targets)
            print(f"[DRY RUN] {len(planned)} target(s) validated successfully (no credits spent):")
            for p in planned:
                print(f"  - Batch: {p['batch']}")
                print(f"    File: {p['file']}")
                print(f"    Region: {p['region']}")
                print(f"    Actor: {p['actor']}")
                print(f"    Keys: {', '.join(p['input_keys'])}")
            return 0

        # Live execution: requires token
        token = runner.token_from_environment_or_prompt(
            prompt=not args.no_prompt,
            token_file=args.token_file,
            token_index=args.token_index,
        )
        print(f"Executing {len(targets)} target(s)...")

        for spec, path in targets:
            print(f"\n--- Running: {spec.file} ({spec.region_id}) ---")
            result = runner.run_file(spec, path, token, import_after=not args.no_import)
            print(f"Completed run: {result['run_id']}")
            print(f"Places saved to: {result['places_path']}")
            if result.get("imported"):
                imp = result["imported"]
                print(f"Importer status: Valid={imp.get('valid_count')}, Failed={imp.get('failed_count')}, Skipped={imp.get('is_skipped', False)}")

        print("\nAll tasks completed successfully.")
        return 0

    except ApifyRunnerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130
    finally:
        runner.close()


if __name__ == "__main__":
    sys.exit(main())
