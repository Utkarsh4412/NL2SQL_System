# Test Results — 20 Questions

| # | Question | SQL Generated | Correct? | Result |
|---|----------|--------------|----------|--------|
| 1 | How many patients do we have? | SELECT COUNT(*) AS total_patients FROM patients | ✅ | 1 row(s) |
| 2 | List all doctors and their specializations | SELECT name, specialization, department FROM doctors ORDER BY specialization | ✅ | 15 row(s) |
| 3 | Show me appointments for last month | SELECT a.id, p.first_name, p.last_name, d.name AS doctor, a.appointment_date, a.status FROM appointments a JOIN patients p ON p.id = a.patient_id JOIN doctors d ON d.id = a.doctor_id WHERE a.appointment_date >= DATE('now','-1 month') ORDER BY a.appointment_date DESC | ✅ | 41 row(s) |
| 4 | Which doctor has the most appointments? | SELECT d.name, COUNT(a.id) AS appointment_count FROM doctors d JOIN appointments a ON a.doctor_id = d.id GROUP BY d.name ORDER BY appointment_count DESC LIMIT 1 | ✅ | 1 row(s) |
| 5 | What is the total revenue? | SELECT SUM(total_amount) AS total_revenue FROM invoices WHERE status = 'Paid' | ✅ | 1 row(s) |
| 6 | Show revenue by doctor | SELECT d.name, SUM(i.total_amount) AS total_revenue FROM invoices i JOIN appointments a ON a.patient_id = i.patient_id JOIN doctors d ON d.id = a.doctor_id WHERE i.status='Paid' GROUP BY d.name ORDER BY total_revenue DESC | ✅ | 15 row(s) |
| 7 | How many cancelled appointments last quarter? | SELECT COUNT(*) AS cancelled_last_quarter FROM appointments WHERE status='Cancelled' AND appointment_date >= DATE('now','-3 months') | ✅ | 1 row(s) |
| 8 | Top 5 patients by spending | SELECT p.first_name, p.last_name, SUM(i.total_amount) AS total_spending FROM invoices i JOIN patients p ON p.id = i.patient_id GROUP BY p.id ORDER BY total_spending DESC LIMIT 5 | ✅ | 5 row(s) |
| 9 | Average treatment cost by specialization | SELECT d.specialization, ROUND(AVG(t.cost),2) AS avg_cost FROM treatments t JOIN appointments a ON a.id = t.appointment_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.specialization ORDER BY avg_cost DESC | ✅ | 5 row(s) |
| 10 | Show monthly appointment count for the past 6 months | SELECT STRFTIME('%Y-%m', appointment_date) AS month, COUNT(*) AS count FROM appointments WHERE appointment_date >= DATE('now','-6 months') GROUP BY month ORDER BY month | ✅ | 7 row(s) |
| 11 | Which city has the most patients? | SELECT city, COUNT(*) AS patient_count FROM patients GROUP BY city ORDER BY patient_count DESC LIMIT 1 | ✅ | 1 row(s) |
| 12 | List patients who visited more than 3 times | SELECT p.id, p.first_name, p.last_name, COUNT(a.id) AS visit_count FROM patients p JOIN appointments a ON a.patient_id = p.id GROUP BY p.id HAVING COUNT(a.id) > 3 ORDER BY visit_count DESC | ✅ | 39 row(s) |
| 13 | Show unpaid invoices | SELECT p.first_name, p.last_name, i.total_amount, i.paid_amount, i.status, i.invoice_date FROM invoices i JOIN patients p ON p.id = i.patient_id WHERE i.status IN ('Pending','Overdue') ORDER BY i.invoice_date | ✅ | 143 row(s) |
| 14 | What percentage of appointments are no-shows? | SELECT ROUND(100.0 * SUM(CASE WHEN status='No-Show' THEN 1 ELSE 0 END) / COUNT(*), 2) AS no_show_percentage FROM appointments | ✅ | 1 row(s) |
| 15 | Show the busiest day of the week for appointments | SELECT CASE STRFTIME('%w', appointment_date) WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday' WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' WHEN '6' THEN 'Saturday' END AS day_of_week, COUNT(*) AS appointment_count FROM appointments GROUP BY STRFTIME('%w', appointment_date) ORDER BY appointment_count DESC LIMIT 1 | ✅ | 1 row(s) |
| 16 | Revenue trend by month | SELECT STRFTIME('%Y-%m', invoice_date) AS month, SUM(total_amount) AS revenue FROM invoices WHERE status='Paid' GROUP BY month ORDER BY month | ✅ | 13 row(s) |
| 17 | Average appointment duration by doctor | SELECT d.name, ROUND(AVG(t.duration_minutes),2) AS avg_duration_minutes FROM treatments t JOIN appointments a ON a.id = t.appointment_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.id ORDER BY avg_duration_minutes DESC | ✅ | 15 row(s) |
| 18 | List patients with overdue invoices | SELECT p.first_name, p.last_name, i.total_amount, i.paid_amount, i.invoice_date FROM invoices i JOIN patients p ON p.id = i.patient_id WHERE i.status='Overdue' ORDER BY i.invoice_date DESC | ✅ | 45 row(s) |
| 19 | Compare revenue between departments | SELECT d.department, SUM(i.total_amount) AS revenue FROM invoices i JOIN appointments a ON a.patient_id = i.patient_id JOIN doctors d ON d.id = a.doctor_id WHERE i.status='Paid' GROUP BY d.department ORDER BY revenue DESC | ✅ | 5 row(s) |
| 20 | Show patient registration trend by month | SELECT STRFTIME('%Y-%m', registered_date) AS month, COUNT(*) AS new_patients FROM patients GROUP BY month ORDER BY month | ✅ | 13 row(s) |

**Score: 20 / 20**

## Failures & explanations

