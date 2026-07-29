from __future__ import annotations
import argparse
import logging
from src.config import ROOT
from src.dataset_generator import generate

def main() -> None:
    parser = argparse.ArgumentParser(description="Portfolio pipeline runner")
    parser.add_argument("--stage", type=int, choices=[1], help="Run legacy Stage 1 dataset generation")
    parser.add_argument("--stages", choices=["dataset", "extraction", "evaluation", "fiverr"], help="Run a named pipeline stage")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    (ROOT/"logs").mkdir(exist_ok=True)
    logging.basicConfig(filename=ROOT/"logs/pipeline.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if args.stages == "extraction":
        from src.pipeline import create_preprocessing_examples, run_extraction
        create_preprocessing_examples()
        summary = run_extraction(force=args.force, limit=24 if args.quick else None)
        print("Stages 2 and 3 extraction pipeline complete")
        for key, value in summary.items():
            if key not in ("development_document_ids", "failures"): print(f"{key}: {value}")
        return
    if args.stages == "evaluation":
        from src.evaluation import run_evaluation
        summary = run_evaluation(force=args.force)
        print("Stage 5 final evaluation complete")
        for key, value in summary.items():
            if not isinstance(value, (dict, list)): print(f"{key}: {value}")
        return
    if args.stages == "fiverr":
        from src.create_fiverr_images import generate
        result = generate()
        print("Stage 6 Fiverr images complete")
        print("validation_passed:", result["all_checks_passed"])
        return
    summary = generate(quick=args.quick, force=args.force)
    print("Stage 1 complete")
    for key, value in summary.items(): print(f"{key}: {value}")
    print("Use --stages extraction for Stages 2 and 3.")

if __name__ == "__main__":
    main()
