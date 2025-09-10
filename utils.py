from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText

def calculate_cycle_length(start, end):
    try:
        start_dt = datetime.strptime(start, '%Y-%m-%d')
        end_dt = datetime.strptime(end, '%Y-%m-%d')
        return (end_dt - start_dt).days + 1
    except ValueError:
        return 1  # Default fallback

def predict_next_period(logs):
    if not logs:
        return None  # No data to predict from

    # Handle both list and database row objects
    try:
        if len(logs) < 2:
            # Use the first entry
            last_log = logs[0]
            if isinstance(last_log, dict):
                last_start = datetime.strptime(last_log['start_date'], '%Y-%m-%d')
            else:
                last_start = datetime.strptime(last_log[2], '%Y-%m-%d')  # Assuming start_date is at index 2
            return last_start + timedelta(days=28)  # fallback to default cycle length

        # Calculate average gap between starts
        gaps = []
        for i in range(min(len(logs)-1, 5)):  # Use only last 5 cycles for better accuracy
            try:
                if isinstance(logs[i], dict):
                    curr = datetime.strptime(logs[i]['start_date'], '%Y-%m-%d')
                    prev = datetime.strptime(logs[i+1]['start_date'], '%Y-%m-%d')
                else:
                    curr = datetime.strptime(logs[i][2], '%Y-%m-%d')
                    prev = datetime.strptime(logs[i+1][2], '%Y-%m-%d')
                
                gap = (curr - prev).days
                if 15 <= gap <= 45:  # Only use reasonable cycle lengths
                    gaps.append(gap)
            except (ValueError, IndexError, KeyError):
                continue

        if not gaps:
            # Fallback if no valid gaps found
            if isinstance(logs[0], dict):
                last_start = datetime.strptime(logs[0]['start_date'], '%Y-%m-%d')
            else:
                last_start = datetime.strptime(logs[0][2], '%Y-%m-%d')
            return last_start + timedelta(days=28)

        avg_cycle = sum(gaps) // len(gaps)
        
        if isinstance(logs[0], dict):
            last_start = datetime.strptime(logs[0]['start_date'], '%Y-%m-%d')
        else:
            last_start = datetime.strptime(logs[0][2], '%Y-%m-%d')
        
        return last_start + timedelta(days=avg_cycle)
        
    except Exception as e:
        print(f"Prediction error: {e}")
        return None

def get_cycle_advice(cycle_length):
    """Provide generic cycle advice based on cycle length"""
    try:
        cycle_length = int(cycle_length)
        if cycle_length <= 3:
            return "💡 Tip: Short cycles (3 days or less) are normal for some women. Stay hydrated and consider tracking symptoms."
        elif cycle_length <= 5:
            return "✨ Great! A 4-5 day cycle is very common. Remember to maintain good nutrition during your period."
        elif cycle_length <= 7:
            return "🌸 Your 6-7 day cycle is perfectly normal. Consider gentle exercise like yoga during this time."
        else:
            return "💭 Longer cycles can be normal too. If you have concerns, consider discussing with a healthcare provider."
    except (ValueError, TypeError):
        return "💡 Cycle tracked successfully! Keep logging to get personalized insights."

def send_email_reminder(to_email, reminder_date, next_start):
    """Send email reminder - currently disabled for demo purposes"""
    try:
        # Dummy Gmail SMTP setup (replace these with your test credentials if needed)
        sender = 'your_email@gmail.com'
        password = 'your_email_password'
        subject = 'Eva Period Tracker Reminder'
        body = f"Hi, this is a reminder that your next period is predicted to start on {next_start.strftime('%d %B %Y')}."

        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = to_email

        # Commenting out actual email sending for demo
        # server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        # server.login(sender, password)
        # server.sendmail(sender, [to_email], msg.as_string())
        # server.quit()
        
        print(f"Email reminder scheduled for {to_email} on {reminder_date}")
        
    except Exception as e:
        print("Email not sent:", e)