#!/usr/bin/env bash
# Builds a realistic 3-commit history for demo/payment_utils.py so WhyCode has evidence to explain.
# Run from the repo root:  bash demo/seed_demo_history.sh
set -e
F=demo/payment_utils.py
mkdir -p demo

commit() {  # $1=author-name $2=email $3=date $4=subject $5=body
  GIT_AUTHOR_NAME="$1" GIT_AUTHOR_EMAIL="$2" GIT_AUTHOR_DATE="$3" \
  GIT_COMMITTER_NAME="$1" GIT_COMMITTER_EMAIL="$2" GIT_COMMITTER_DATE="$3" \
  git commit -q -m "$4" -m "$5"
}

# --- v1: simple feature ---
cat > $F << 'PY'
def calculate_gateway_amount(price, tax_rate):
    """Amount (in paise) to send to the payment gateway."""
    total = price * (1 + tax_rate)
    return int(total * 100)
PY
git add $F
commit "Riya Sharma" "riya@example.com" "2025-01-10T10:00:00" \
  "Add calculate_gateway_amount" "Initial implementation for checkout flow."

# --- v2: bug fix ---
cat > $F << 'PY'
def calculate_gateway_amount(price, tax_rate):
    """Amount (in paise) to send to the payment gateway."""
    total = price * (1 + tax_rate)
    # NOTE: round() before int(), float truncation was losing 1 paisa
    return int(round(total * 100))
PY
git add $F
commit "Amit Verma" "amit@example.com" "2025-03-02T15:30:00" \
  "Fix off-by-one paisa in gateway amount (#142)" \
  "int(19.99 * 100) gave 1998 instead of 1999, so the gateway rejected the signature check and customers were double-charged on retry. Round before converting. Regression of #142."

# --- v3: workaround for gateway quirk ---
cat > $F << 'PY'
def calculate_gateway_amount(price, tax_rate, currency="INR"):
    """Amount (in paise) to send to the payment gateway."""
    total = price * (1 + tax_rate)
    # NOTE: round() before int(), float truncation was losing 1 paisa
    amount = int(round(total * 100))
    # HACK: gateway rejects amounts below 100 paise (INC-2291), do not remove
    if currency == "INR" and amount < 100:
        amount = 100
    return amount
PY
git add $F
commit "Neha Gupta" "neha@example.com" "2025-06-18T12:45:00" \
  "Workaround: enforce 100 paise minimum for INR (INC-2291)" \
  "Gateway returns 4xx for sub-rupee amounts in production. Temporary workaround until the gateway fixes this on their side. Compliance requires we never send such requests. Backward compatible with existing callers."

echo "Done. Now run: git push"
git log --oneline -- $F
