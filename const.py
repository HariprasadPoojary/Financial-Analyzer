# ── Column name aliases (case-insensitive matching) ────────────────────────────
DATE_ALIASES = ["Date", "Tran Date"]
DESCRIPTION_ALIASES = ["PARTICULARS", "Details"]
DEBIT_ALIASES = ["Debit", "CR"]
CREDIT_ALIASES = ["Credit", "DR"]
BALANCE_ALIASES = ["Balance", "BAL"]

# ── Category rules: (category, [keywords/patterns], transaction_type)
# Order matters — more specific rules should come first.
# transaction_type: "credit", "debit", or "both" (default)
CATEGORY_RULES: list[tuple[str, list[str], str]] = [
    # Income - only for credits
    (
        "Income",
        [
            r"\bsalary\b",
            r"\bSALARY\b",
            r"\bACH-CR\b",
            r"\bIMPS/P2A\b",
            r"\bMBB-TD/\b",
            r"\bNEFT\b",
            r"\bUPI/CR\b",
            r"\bSB:\b",
        ],
        "credit",
    ),
    # Housing
    (
        "Housing",
        [
            r"\brent\b",
            r"\bBABITHA  MANJUNATH   /\b",
        ],
        "debit",
    ),
    # Groceries
    (
        "Groceries",
        [
            r"\bZepto\b",
            r"\btrader joe",
            r"\bkroger\b",
            r"\bsafeway\b",
            r"\baldi\b",
            r"\bwegmans\b",
            r"\bpublix\b",
            r"\bcostco\b",
            r"\bwaitrose\b",
            r"\btesco\b",
            r"\bsainsbury\b",
            r"\basda\b",
            r"\blidl\b",
            r"\bmorrisons\b",
            r"\bsupermarket\b",
            r"\bgrocery\b",
            r"\bfood store\b",
            r"\bmarket\b",
        ],
        "debit",
    ),
    # Dining & Restaurants
    (
        "Dining",
        [
            r"\brestaurant\b",
            r"\bcafe\b",
            r"\bZomato\b",
            r"\bDominos\b",
        ],
        "debit",
    ),
    # Transport
    (
        "Transport",
        [
            r"\buber\b",
            r"\bRedbus\b",
        ],
        "debit",
    ),
    # Utilities
    (
        "Utilities",
        [
            r"\belectric\b",
            r"\bgas bill\b",
            r"\bwater bill\b",
            r"\binternet\b",
            r"\bbroadband\b",
            r"\bphone\b",
            r"\bmobile\b",
            r"\bbt group\b",
            r"\bvirgin media\b",
            r"\bpge\b",
            r"\bcon edison\b",
            r"\bcouncil tax\b",
            r"\brates\b",
        ],
        "debit",
    ),
    # Subscriptions & Entertainment
    (
        "Subscriptions & Entertainment",
        [
            r"\bnetflix\b",
            r"\bDISTRICT\b",
            r"\bbookmyshow\b",
        ],
        "debit",
    ),
    # Shopping
    (
        "Shopping",
        [
            r"\bamazon\b",
            r"\bCreditCard Payment\b",
        ],
        "debit",
    ),
    # ATM & Cash
    (
        "Cash & ATM",
        [
            r"\bATMCard\b",
        ],
        "debit",
    ),
    # Transfers
    (
        "UPI & Transfers",
        [
            r"\bUPI/\b",
            r"\bUPI/CR\b",
            r"\bRAZORPAY/\b",
            r"\bNEFT/\b",
            r"\bUPILITE\b",
        ],
        "both",
    ),
    # Investments
    (
        "Investments",
        [
            r"\bMutual Funds\b",
            r"\bGroww\b",
            r"\bPPF\b",
            r"\bRD/\b",
            r"\bACH-DR-Groww\b",
            r"\bLIC OF INDIA\b",
            r"\bECS/UTIBDE34161840202601\b",
            r"\bWEALTHYIN CUSTOMER\b",
            r"\bethereum\b",
        ],
        "debit",
    ),
    # EMI
    (
        "EMI",
        [
            r"_EMI_",
        ],
        "debit",
    ),
]
