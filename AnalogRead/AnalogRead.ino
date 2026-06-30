#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>

// LCD pins (same as main firmware)
#define LCD_MOSI 23
#define LCD_SCLK 18
#define LCD_CS   15
#define LCD_DC    2
#define LCD_RST   4
#define LCD_BLK  32
#define LCD_BRIGHTNESS 25

Adafruit_ST7789 tft = Adafruit_ST7789(LCD_CS, LCD_DC, LCD_RST);

static int prevVal12 = -1;
static int prevVal14 = -1;

void setup() {
  Serial.begin(115200);
  analogSetAttenuation(ADC_11db);
  pinMode(12, INPUT);
  pinMode(14, INPUT);

  // Init display
  pinMode(LCD_BLK, OUTPUT);
  analogWrite(LCD_BLK, LCD_BRIGHTNESS);
  tft.init(170, 320);
  tft.setRotation(1);
  tft.setSPISpeed(80000000);
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextWrap(false);
}

void loop() {
  int val12 = analogRead(12);
  int val14 = analogRead(14);

  Serial.print("Pin12:");
  Serial.print(val12);
  Serial.print(",Pin14:");
  Serial.println(val14);

  // Display on LCD only if values changed
  if (val12 != prevVal12 || val14 != prevVal14) {
    tft.fillScreen(ST77XX_BLACK);
    tft.setTextSize(3);

    tft.setCursor(10, 40);
    tft.print("A (12): ");
    tft.println(val12);

    tft.setCursor(10, 90);
    tft.print("B (14): ");
    tft.println(val14);

    prevVal12 = val12;
    prevVal14 = val14;
  }

  delay(100);
}
