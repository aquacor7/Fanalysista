"""
Download formations xlsx for every giornata in a (league, competition).

Resumes by default: if a giornata's xlsx already exists in the bronze folder
and is non-trivial size, it's skipped. Pass --force to re-download everything.

Usage:
    python download_all.py -l "My League" -c "Serie C"
    python download_all.py -l "My League" -c "Serie C" -t "My Team"
    python download_all.py -l "My League" -c "Serie C" --force
"""
import argparse
import time

from cli import add_common_args, login_and_select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    parser.add_argument(
        "--min-bytes", type=int, default=1024,
        help="Skip downloads smaller than this many bytes (default: 1024)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-download even if a file for that giornata already exists",
    )
    args = parser.parse_args()

    client, _league, comp, out_dir = login_and_select(args)

    rounds = client.get_competition_rounds(comp.id)
    if not rounds:
        print(
            f"[rounds]     0 configured for {comp.name!r} "
            f"(id={comp.id}) — nothing to download.\n"
            f"             The competition has no calendar yet, or it's archived. "
            f"Try a different competition in this league."
        )
        return
    print(f"[rounds]     {len(rounds)} configured: {rounds[0]}..{rounds[-1]}")
    out_dir.mkdir(parents=True, exist_ok=True)

    saved, skipped_existing, skipped_empty, failed = [], [], [], []

    for r in rounds:
        # The server's filename pattern is "Formazioni_{alias}_{N}_giornata.xlsx".
        # Glob locally to detect a previous successful download.
        existing = list(out_dir.glob(f"Formazioni_*_{r}_giornata.xlsx"))
        if existing and not args.force and existing[0].stat().st_size >= args.min_bytes:
            print(f"  g{r:>2}: already on disk ({existing[0].name}, "
                  f"{existing[0].stat().st_size} B) — skipping. "
                  f"Use --force to re-download.")
            skipped_existing.append(r)
            continue

        t0 = time.monotonic()
        print(f"  g{r:>2}: downloading...", end=" ")
        try:
            path = client.download_formations(comp.id, r, out_dir=out_dir)
        except Exception as e:
            print(f"FAILED - {type(e).__name__}: {e}")
            failed.append(r)
            continue

        size = path.stat().st_size
        elapsed = time.monotonic() - t0
        if size < args.min_bytes:
            path.unlink()
            print(f"empty ({size} B in {elapsed:.1f}s), discarded")
            skipped_empty.append(r)
        else:
            print(f"{path.name} ({size} B in {elapsed:.1f}s)")
            saved.append(r)

    print()
    print(f"[done] saved={len(saved)} "
          f"skipped_existing={len(skipped_existing)} "
          f"skipped_empty={len(skipped_empty)} "
          f"failed={len(failed)}")
    print(f"       out: {out_dir}/")
    if failed:
        print(f"       retry failed giornate: {failed}")


if __name__ == "__main__":
    main()
