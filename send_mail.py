import smtplib
import csv
import re
from email.mime.text import MIMEText

sender_email = "your email here"
app_password = "your app password here"

subject = "Data Analyst Internship Opportunity"

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()
server.login(sender_email, app_password)

email_pattern = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

with open("emails.csv", newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    for row in reader:
        name = row["Name"]
        email = row["Email"]
        company = row["Company"]

        if not email_pattern.match(email):
            print("Skipped invalid email:", email)
            continue
        

        body = f"""Hi {name},

I came across {company}'s Data Analytics Internship opening on LinkedIn and wanted to reach out directly.

I'm Aditya Raj, a B.Tech student at Invertis University (2023-27, CGPA: 7.9) with hands-on experience in Python, SQL, Power BI, and DAX. A few things I've built recently:

- A Power BI dashboard with 10+ visuals for Super Store Sales & Profit analysis (YoY trends, KPIs using DAX)
- A PostgreSQL-based Bookstore Sales Analytics project with 15+ complex queries (joins, aggregations, revenue trends)
- A full Retail EDA using Pandas, NumPy, and Scikit-learn with heatmaps and outlier detection

I also completed the Deloitte Data Analytics Job Simulation (Forage) and hold certifications in Python (IBM), Power BI, and SQL.

I'm available for a 3-6 month internship immediately . I'd love to contribute to {company}'s data team.

Would you be open to a quick 10-minute call, or shall I send my resume for review?

Best regards,
Aditya Raj 
"""

        msg = MIMEText(body, _charset="utf-8")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = email

        server.sendmail(sender_email, email, msg.as_string())
        print("Sent to:", email)

server.quit()
