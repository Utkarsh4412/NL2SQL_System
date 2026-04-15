import os
import random
import sqlite3
from datetime import date, datetime, timedelta

from faker import Faker


DB_PATH = os.environ.get("CLINIC_DB_PATH", "clinic.db")


def rand_date(days_back: int = 365) -> datetime:
    """Return a random datetime within the past `days_back` days."""
    days = random.randint(0, max(0, days_back))
    seconds = random.randint(0, 24 * 60 * 60 - 1)
    return datetime.now() - timedelta(days=days, seconds=seconds)


def maybe_null(value, prob: float = 0.15):
    return None if random.random() < prob else value


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _drop_all(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS treatments;
        DROP TABLE IF EXISTS appointments;
        DROP TABLE IF EXISTS invoices;
        DROP TABLE IF EXISTS doctors;
        DROP TABLE IF EXISTS patients;
        """
    )


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE patients (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          first_name TEXT NOT NULL,
          last_name TEXT NOT NULL,
          email TEXT,
          phone TEXT,
          date_of_birth DATE,
          gender TEXT CHECK(gender IN ('M','F')),
          city TEXT,
          registered_date DATE
        );

        CREATE TABLE doctors (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          specialization TEXT,
          department TEXT,
          phone TEXT
        );

        CREATE TABLE appointments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          patient_id INTEGER REFERENCES patients(id),
          doctor_id INTEGER REFERENCES doctors(id),
          appointment_date DATETIME,
          status TEXT CHECK(status IN ('Scheduled','Completed','Cancelled','No-Show')),
          notes TEXT
        );

        CREATE TABLE treatments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          appointment_id INTEGER REFERENCES appointments(id),
          treatment_name TEXT,
          cost REAL,
          duration_minutes INTEGER
        );

        CREATE TABLE invoices (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          patient_id INTEGER REFERENCES patients(id),
          invoice_date DATE,
          total_amount REAL,
          paid_amount REAL,
          status TEXT CHECK(status IN ('Paid','Pending','Overdue'))
        );
        """
    )


SPECIALIZATIONS = ["Dermatology", "Cardiology", "Orthopedics", "General", "Pediatrics"]

TREATMENTS_BY_SPEC = {
    "Dermatology": [
        "Acne Treatment",
        "Laser Therapy",
        "Biopsy",
        "Skin Allergy Test",
        "Botox",
    ],
    "Cardiology": ["ECG", "Echocardiogram", "Angioplasty", "Stress Test", "Blood Panel"],
    "Orthopedics": [
        "X-Ray",
        "MRI Scan",
        "Joint Injection",
        "Physiotherapy",
        "Fracture Cast",
    ],
    "General": [
        "General Checkup",
        "Blood Test",
        "Vaccination",
        "Urine Analysis",
        "BP Check",
    ],
    "Pediatrics": [
        "Well-Child Visit",
        "Immunization",
        "Growth Assessment",
        "Ear Exam",
        "Flu Shot",
    ],
}

INDIAN_CITIES = [
    "Mumbai",
    "Delhi",
    "Bangalore",
    "Hyderabad",
    "Chennai",
    "Kolkata",
    "Pune",
    "Jaipur",
    "Ahmedabad",
    "Surat",
]


def main() -> None:
    random.seed(42)
    Faker.seed(42)
    fake = Faker("en_IN")

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = _connect(DB_PATH)
    try:
        _drop_all(conn)
        _create_schema(conn)

        # Doctors: 15 across 5 specializations (3 each)
        doctors = []
        for spec in SPECIALIZATIONS:
            for _ in range(3):
                name = fake.name()
                doctors.append(
                    (
                        name,
                        spec,
                        spec,  # department aligned to specialization for reporting
                        maybe_null(fake.phone_number()),
                    )
                )
        conn.executemany(
            "INSERT INTO doctors(name, specialization, department, phone) VALUES (?,?,?,?)",
            doctors,
        )

        # Patients: 200 across Indian cities
        patients = []
        genders = ["M", "F"]
        for _ in range(200):
            first = fake.first_name()
            last = fake.last_name()
            email = maybe_null(fake.email())
            phone = maybe_null(fake.phone_number())
            dob = (date.today() - timedelta(days=random.randint(18 * 365, 85 * 365))).isoformat()
            gender = random.choice(genders)
            city = random.choice(INDIAN_CITIES)
            registered = rand_date(365).date().isoformat()
            patients.append((first, last, email, phone, dob, gender, city, registered))
        conn.executemany(
            """
            INSERT INTO patients(first_name,last_name,email,phone,date_of_birth,gender,city,registered_date)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            patients,
        )

        patient_ids = [r[0] for r in conn.execute("SELECT id FROM patients ORDER BY id").fetchall()]
        doctor_rows = conn.execute("SELECT id, specialization FROM doctors ORDER BY id").fetchall()
        doctor_ids = [r[0] for r in doctor_rows]
        doctor_spec = {doc_id: spec for doc_id, spec in doctor_rows}

        # Appointment distribution: top 20 patients 8x, next 40 patients 3x
        weights = []
        for idx, _pid in enumerate(patient_ids):
            if idx < 20:
                weights.append(8)
            elif idx < 60:
                weights.append(3)
            else:
                weights.append(1)

        statuses = ["Scheduled", "Completed", "Cancelled", "No-Show"]
        status_weights = [0.25, 0.55, 0.13, 0.07]

        appointments = []
        for _ in range(500):
            patient_id = random.choices(patient_ids, weights=weights, k=1)[0]
            doctor_id = random.choice(doctor_ids)
            appt_dt = rand_date(365).strftime("%Y-%m-%d %H:%M:%S")
            status = random.choices(statuses, weights=status_weights, k=1)[0]
            notes = maybe_null(fake.sentence(nb_words=8))
            appointments.append((patient_id, doctor_id, appt_dt, status, notes))
        conn.executemany(
            """
            INSERT INTO appointments(patient_id,doctor_id,appointment_date,status,notes)
            VALUES (?,?,?,?,?)
            """,
            appointments,
        )

        # Treatments: 350 linked ONLY to Completed appointments
        completed = conn.execute(
            "SELECT id, doctor_id FROM appointments WHERE status = 'Completed'"
        ).fetchall()
        if len(completed) == 0:
            raise RuntimeError("No completed appointments available to attach treatments.")

        treatments = []
        for _ in range(350):
            appt_id, doc_id = random.choice(completed)
            spec = doctor_spec.get(doc_id, "General")
            treatment_name = random.choice(TREATMENTS_BY_SPEC.get(spec, TREATMENTS_BY_SPEC["General"]))
            cost = round(random.uniform(50, 5000), 2)
            duration = random.choice([10, 15, 20, 30, 45, 60, 75, 90])
            treatments.append((appt_id, treatment_name, cost, duration))
        conn.executemany(
            """
            INSERT INTO treatments(appointment_id,treatment_name,cost,duration_minutes)
            VALUES (?,?,?,?)
            """,
            treatments,
        )

        # Invoices: 300 with Paid/Pending/Overdue split (55/30/15)
        invoice_statuses = ["Paid", "Pending", "Overdue"]
        invoice_weights = [0.55, 0.30, 0.15]
        invoices = []
        for _ in range(300):
            patient_id = random.choice(patient_ids)
            invoice_dt = rand_date(365).date().isoformat()
            total = round(random.uniform(50, 5000), 2)
            status = random.choices(invoice_statuses, weights=invoice_weights, k=1)[0]
            if status == "Paid":
                paid = total
            elif status == "Pending":
                paid = round(random.uniform(0, total * 0.5), 2)
            else:  # Overdue
                paid = 0.0
            invoices.append((patient_id, invoice_dt, total, paid, status))
        conn.executemany(
            """
            INSERT INTO invoices(patient_id,invoice_date,total_amount,paid_amount,status)
            VALUES (?,?,?,?,?)
            """,
            invoices,
        )

        conn.commit()

        p_count = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        d_count = conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]
        a_count = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
        t_count = conn.execute("SELECT COUNT(*) FROM treatments").fetchone()[0]
        i_count = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]

        print(
            f"Created {p_count} patients, {d_count} doctors, {a_count} appointments, "
            f"{t_count} treatments, {i_count} invoices -> {DB_PATH}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()

