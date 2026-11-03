def calculate_gateway_amount(price, tax_rate, currency="INR"):
    """Amount (in paise) to send to the payment gateway."""
    total = price * (1 + tax_rate)
    # NOTE: round() before int(), float truncation was losing 1 paisa
    amount = int(round(total * 100))
    # HACK: gateway rejects amounts below 100 paise (INC-2291), do not remove
    if currency == "INR" and amount < 100:
        amount = 100
    return amount
