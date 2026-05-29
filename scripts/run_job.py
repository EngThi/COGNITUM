import sys
import importlib
from automations.log import get_logger

logger = get_logger("runner")

def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/run_job.py module.path")
    module_name = sys.argv[1]
    module = importlib.import_module(module_name)
    if not hasattr(module, "run"):
        raise SystemExit(f"Module {module_name} missing run()")
    logger.info("Running job: %s", module_name)
    result = module.run()
    logger.info("Finished: %s", result)

if __name__ == "__main__":
    main()
