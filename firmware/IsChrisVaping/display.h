#ifndef DISPLAY_H
#define DISPLAY_H

#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>

// LCD pins
#define LCD_MOSI 23
#define LCD_SCLK 18
#define LCD_CS   15
#define LCD_DC    2
#define LCD_RST   4
#define LCD_BLK  32
#define LCD_BRIGHTNESS 25

// At textSize=7: 42px wide, 56px tall per char
static constexpr uint8_t textSize = 6;
static constexpr uint8_t charW = 6 * textSize;
static constexpr uint8_t charH = 8 * textSize;
static constexpr uint8_t lineSpacing = 2;

extern Adafruit_ST7789 tft;
extern const char* currentDisplayText;

#define BT_X_OFFSET 10
#define BT_Y_OFFSET 10

static constexpr int16_t vapeNameXOffset = 2;
static constexpr int16_t vapeNameYOffset = 2;

void displayInit();
void showText(const char* text);
void drawBtIcon();
void drawVapeName();

#endif
