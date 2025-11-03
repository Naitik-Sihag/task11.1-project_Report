# -*- coding: utf-8 -*-
import serial, time, threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import firebase_admin
from firebase_admin import credentials, db
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from collections import deque
import speech_recognition as sr  # <-- added for voice commands

# ---------------- FIREBASE SETUP ----------------
cred = credentials.Certificate("/home/pi/smartstretcher-key.json")  # <-- update path
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://patient-health-monitorin-48758-default-rtdb.firebaseio.com/"  # <-- update your URL
})
# ---------------- SERIAL SETUP ----------------
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 115200
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print("? Connected to Arduino")
except Exception as e:
    print("? Serial error:", e)
    exit()

# ---------------- VOICE COMMAND ----------------
def listen_for_start():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    print("Say 'start' to launch the monitoring dashboard...")
    while True:
        try:
            with mic as source:
                recognizer.adjust_for_ambient_noise(source)
                audio = recognizer.listen(source)
            text = recognizer.recognize_google(audio)
            print("Heard:", text)
            if "start" in text.lower():
                print("Starting dashboard...")
                break
        except sr.UnknownValueError:
            pass
        except sr.RequestError as e:
            print("Speech Recognition error:", e)
        except Exception as e:
            print("Error:", e)

# Wait for voice command before opening GUI
listen_for_start()

# ---------------- GUI SETUP ----------------
root = tk.Tk()
root.title("Smart Stretcher Dashboard")
root.geometry("950x750")
root.configure(bg="#0a0f1f")

style = ttk.Style()
style.theme_use("clam")
style.configure("TLabel", foreground="#00ffe0", background="#0a0f1f", font=("Consolas", 12))
style.configure("Title.TLabel", font=("Orbitron", 22, "bold"), foreground="#00ffcc", background="#0a0f1f")
style.configure("TButton", font=("Consolas", 11), background="#00ffe0")

ttk.Label(root, text="? Smart Stretcher Monitoring System", style="Title.TLabel").pack(pady=10)
# ---------------- PATIENT INFO ----------------
patient_frame = ttk.LabelFrame(root, text="Patient Info", padding=15)
patient_frame.pack(padx=15, pady=10, fill="x")

ttk.Label(patient_frame, text="Name:").grid(row=0, column=0, sticky="e", padx=5)
ttk.Label(patient_frame, text="Age:").grid(row=0, column=2, sticky="e", padx=5)
ttk.Label(patient_frame, text="Gender:").grid(row=0, column=4, sticky="e", padx=5)

entry_name = ttk.Entry(patient_frame, width=20)
entry_age = ttk.Entry(patient_frame, width=10)
entry_gender = ttk.Combobox(patient_frame, values=["Male","Female","Other"], width=10)

entry_name.grid(row=0, column=1, padx=5)
entry_age.grid(row=0, column=3, padx=5)
entry_gender.grid(row=0, column=5, padx=5)

current_patient = None

def save_patient():
    global current_patient
    name = entry_name.get().strip()
    age = entry_age.get().strip()
    gender = entry_gender.get().strip()
    if not name or not age or not gender:
        messagebox.showwarning("Missing Info","Please fill all patient details.")
        return
    patient_id = name.replace(" ","_")
    current_patient = db.reference(f"patients/{patient_id}")
    current_patient.update({"name": name,"age": age,"gender": gender})
    messagebox.showinfo("Saved",f"Monitoring {name}")
    print(f"? Monitoring {name}")

ttk.Button(patient_frame,text="Save Patient",command=save_patient).grid(row=0,column=6,padx=10)

# ---------------- SENSOR DISPLAY ----------------
sensor_frame = ttk.LabelFrame(root,text="Live Sensor Data",padding=15)
sensor_frame.pack(padx=15,pady=10,fill="x")

SENSOR_KEYS = ["Temp","Humidity","AngleX","AngleY","Distance","Pulse","LED","Buzzer","Bed"]
labels = {}
for i,key in enumerate(SENSOR_KEYS):
    ttk.Label(sensor_frame,text=f"{key}:").grid(row=i,column=0,sticky="e",padx=10,pady=4)
    labels[key] = ttk.Label(sensor_frame,text="--",width=20)
    labels[key].grid(row=i,column=1,sticky="w")

timestamp_label = ttk.Label(root,text="Last updated: --")
timestamp_label.pack(pady=5)

# ---------------- LIVE GRAPHS ----------------
graph_frame = ttk.LabelFrame(root,text="Live Graphs",padding=15)
graph_frame.pack(padx=15,pady=10,fill="both",expand=True)

fig, (ax1, ax2) = plt.subplots(2,1,figsize=(7,5),dpi=100)
fig.patch.set_facecolor("#0a0f1f")
for ax in [ax1,ax2]:
    ax.set_facecolor("#10172a")
    ax.tick_params(colors="white")
    for spine in ax.spines.values(): spine.set_color("#00ffe0")
ax1.set_title("Temperature (*C)",color="#00ffe0")
ax2.set_title("Humidity (%)",color="#00ffe0")

temp_data = deque(maxlen=30)
hum_data = deque(maxlen=30)
time_data = deque(maxlen=30)

temp_line, = ax1.plot([],[],color="#00ff99")
hum_line, = ax2.plot([],[],color="#00aaff")

canvas = FigureCanvasTkAgg(fig,master=graph_frame)
canvas.get_tk_widget().pack(fill="both",expand=True)

# ---------------- LOG TEXT ----------------
text_box = tk.Text(root,height=6,bg="#050a15",fg="#00ff99",font=("Consolas",10))
text_box.pack(fill="x",padx=15,pady=10)
# ---------------- SERIAL LOOP ----------------
def serial_loop():
    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode("utf-8").strip()
                if line:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    text_box.insert("end",f"[{timestamp}] {line}\n")
                    text_box.see("end")
                    timestamp_label.config(text=f"Last updated: {timestamp}")

                    # Robust parsing (keep exact keys)
                    parts = line.split(',')
                    data = {}
                    for part in parts:
                        if ':' in part:
                            key, val = part.split(':',1)
                            key = key.strip()  # do NOT use .title()
                            val = val.strip()
                            data[key] = val

                    # Update GUI labels
                    for key in SENSOR_KEYS:
                        if key in data:
                            labels[key].config(text=data[key])

                    # Update graphs
                    if "Temp" in data and "Humidity" in data:
                        try:
                            temp_data.append(float(data["Temp"]))
                            hum_data.append(float(data["Humidity"]))
                            time_data.append(len(time_data))
                            temp_line.set_data(time_data,temp_data)
                            hum_line.set_data(time_data,hum_data)
                            ax1.relim(); ax1.autoscale_view()
                            ax2.relim(); ax2.autoscale_view()
                            canvas.draw_idle()
                        except: pass

                    # Upload to Firebase
                    if current_patient:
                        current_patient.child("readings").push().set({**data,"timestamp":timestamp})

        except Exception as e:
            text_box.insert("end",f"[Error] {e}\n")
            text_box.see("end")
        time.sleep(2)  # match Arduino delay

threading.Thread(target=serial_loop,daemon=True).start()
root.mainloop()
