#include "display.h"
#include "bluetooth.h"
#include "bluetooth_connected.h"
#include "bluetooth_disconnected.h"

Adafruit_ST7789 tft = Adafruit_ST7789(LCD_CS, LCD_DC, LCD_RST);
const char* currentDisplayText = "NOT\nRIPPED";

void displayInit() {
  pinMode(LCD_BLK, OUTPUT);
  analogWrite(LCD_BLK, LCD_BRIGHTNESS);
  tft.init(170, 320);
  tft.writeCommand(ST77XX_DISPON);
  tft.setRotation(1);
  tft.setSPISpeed(80000000);  // 80MHz SPI
  tft.fillScreen(ST77XX_BLACK);
  showText("NOT\nRIPPED");
}

void drawBtIcon() {
  const uint8_t* btBitmap = deviceConnected ? bluetooth_connected : bluetooth_disconnected;
  uint16_t w = bluetooth_connected_width;
  uint16_t h = bluetooth_connected_height;

  // Clear the icon area and draw the new icon
  tft.fillRect(0, 0, w + 2, h + 2, ST77XX_BLACK);
  tft.drawBitmap(1, 1, btBitmap, w, h, ST77XX_WHITE);
}

void showText(const char* text) {
  currentDisplayText = text;

  tft.fillScreen(ST77XX_BLACK);

  // Count lines and find max line length
  uint8_t lineCount = 1;
  const char* p = text;
  while (*p) { if (*p == '\n') lineCount++; p++; }

  // Calculate total text block height
  uint16_t totalH = lineCount * charH + (lineCount - 1) * lineSpacing;
  int16_t startY = (170 - totalH) / 2;

  tft.setTextSize(textSize);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextWrap(false);

  // Draw each line centered
  const char* lineStart = text;
  for (uint8_t line = 0; line < lineCount; line++) {
    // Find end of this line
    const char* lineEnd = lineStart;
    while (*lineEnd && *lineEnd != '\n') lineEnd++;
    uint8_t lineLen = lineEnd - lineStart;

    int16_t x = (320 - lineLen * charW) / 2;
    int16_t y = startY + line * (charH + lineSpacing);

    tft.setCursor(x, y);
    for (uint8_t i = 0; i < lineLen; i++) {
      tft.write(lineStart[i]);
    }

    lineStart = (*lineEnd == '\n') ? lineEnd + 1 : lineEnd;
  }

  drawBtIcon();
  drawVapeName();
}

void drawVapeName() {
  // Draw the vape name in small font at bottom-left
  uint8_t nameSize = 1;
  uint8_t nameCharW = 6 * nameSize;
  uint8_t nameCharH = 8 * nameSize;
  int16_t x = 2;
  int16_t y = 170 - nameCharH - 2;

  // Clear the bottom-left area
  tft.fillRect(0, y - 1, strlen(vapeName) * nameCharW + 4, nameCharH + 3, ST77XX_BLACK);

  tft.setTextSize(nameSize);
  tft.setTextColor(ST77XX_WHITE);
  tft.setCursor(x, y);
  tft.print(vapeName);
}
