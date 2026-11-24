def send_notification(
    recipient_email: str,
    subject: str,
    message: str,
):
    print("\n========== NOTIFICATION ==========")
    print(f"To: {recipient_email}")
    print(f"Subject: {subject}")
    print(f"Message: {message}")
    print("==================================\n")