import logging

from app.logging_utils import instrument_module_functions


def main():
    print("Hello from stmdb!")


if __name__ == "__main__":
    main()


instrument_module_functions(globals(), logging.getLogger("smtdb.main"), exclude={"instrument_module_functions"})
