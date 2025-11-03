#include <Arduino_LSM6DS3.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>

// ===== PINS =====
#define DHTPIN 2
#define DHTTYPE DHT11
#define TRIG_PIN 6
#define ECHO_PIN 7
#define BUZZER_PIN 8
#define LED_PIN 9
#define PULSE_PIN A0

// ===== OBJECTS =====
DHT dht(DHTPIN, DHTTYPE);

// ===== GLOBAL VARIABLES =====
float temperature = 0;
float humidity = 0;
float angleX = 0;
float angleY = 0;
long distance = 0;
int pulseValue = 0;
float accX, accY, accZ;

// ===== SETUP =====
void setup() {
  Serial.begin(115200);
  delay(2000); // sensor startup

  dht.begin();
  delay(1000);

  if (!IMU.begin()) {
    Serial.println("⚠️ IMU failed");
    while(1);
  }

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  pinMode(PULSE_PIN, INPUT);

  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(LED_PIN, LOW);

  Serial.println("✅ Smart Stretcher System Ready");
}

// ===== LOOP =====
void loop() {
  readDHT();
  readIMU();
  readUltrasonic();
  readPulse();

  // LED for tilt
  if(abs(angleX)>15 || abs(angleY)>15) digitalWrite(LED_PIN,HIGH);
  else digitalWrite(LED_PIN,LOW);

  // Buzzer for distance
  if(distance>0 && distance<15) digitalWrite(BUZZER_PIN,HIGH);
  else digitalWrite(BUZZER_PIN,LOW);

  // Serial output
  Serial.print("Temp:"); Serial.print(temperature,1);
  Serial.print(",Humidity:"); Serial.print(humidity,1);
  Serial.print(",AngleX:"); Serial.print(angleX,1);
  Serial.print(",AngleY:"); Serial.print(angleY,1);
  Serial.print(",Distance:"); Serial.print(distance);
  Serial.print(",Pulse:"); Serial.print(pulseValue);
  Serial.print(",LED:"); Serial.print(digitalRead(LED_PIN)?"ON":"OFF");
  Serial.print(",Buzzer:"); Serial.println(digitalRead(BUZZER_PIN)?"ON":"OFF");

  delay(2000); // DHT stabilization
}

// ===== FUNCTIONS =====

// --- DHT11 Reading with Retry
void readDHT() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();

  if(isnan(t) || isnan(h)) {
    delay(1000);
    t = dht.readTemperature();
    h = dht.readHumidity();
  }

  if(!isnan(t) && !isnan(h)) {
    temperature = t;
    humidity = h;
  } else {
    Serial.println("⚠️ DHT11 read failed, using last value");
  }
}

// --- IMU Reading (built-in)
void readIMU() {
  if(IMU.accelerationAvailable()) {
    IMU.readAcceleration(accX, accY, accZ);
    angleX = atan(accX / sqrt(pow(accY,2)+pow(accZ,2)))*57.2958;
    angleY = atan(accY / sqrt(pow(accX,2)+pow(accZ,2)))*57.2958;
  }
}

// --- Ultrasonic Reading (HW-827)
void readUltrasonic() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(5);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long dur = pulseIn(ECHO_PIN,HIGH,30000); // 30ms timeout
  distance = (dur==0) ? -1 : dur*0.034/2; // cm
}

// --- Pulse Sensor Reading
void readPulse() {
  pulseValue = analogRead(PULSE_PIN); // 0-1023
}
