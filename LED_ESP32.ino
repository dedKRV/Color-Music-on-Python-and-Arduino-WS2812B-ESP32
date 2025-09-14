#include <Adafruit_NeoPixel.h> //https://github.com/dedKRV/Color-Music-on-Python-and-Arduino-WS2812B-ESP32
#define LED_PIN 16
#define NUM_LEDS 300

Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

struct Config {
    uint8_t mode;
    uint8_t base_r, base_g, base_b;
    uint8_t low_r, low_g, low_b;
    uint8_t high_r, high_g, high_b;
    float low_level;
    float high_level;
    float threshold;
    float gradient_pos;
    uint8_t gradient_speed;
};

Config config;
unsigned long lastGradientUpdate = 0;

void setup() {
    Serial.begin(115200);
    strip.begin();
    strip.show();
    resetConfig();
}

void loop() {
    if (Serial.available() > 0) {
        String data = Serial.readStringUntil('\n');
        data.trim();
        parseCommand(data);
        updateLEDs();
    }
    
    // Автоматическое обновление градиента
    if (config.mode == 3) {
        updateGradient();
    }
}

void resetConfig() {
    config.mode = 0;
    config.base_r = 30; config.base_g = 0; config.base_b = 50;
    config.low_r = 255; config.low_g = 0; config.low_b = 100;
    config.high_r = 100; config.high_g = 0; config.high_b = 255;
    config.threshold = 0.1;
    config.gradient_pos = 0;
    config.gradient_speed = 50;
}

void parseCommand(String data) {
    if (data.charAt(0) == 'B') {
        sscanf(data.c_str(), "B%hhu,%hhu,%hhu", 
            &config.base_r, &config.base_g, &config.base_b);
        return;
    }
    
    if (data.charAt(0) == 'G') {
        // Команда градиента
        sscanf(data.c_str(), "G%f;B%hhu,%hhu,%hhu;L%hhu,%hhu,%hhu;H%hhu,%hhu,%hhu;S%hhu",
            &config.gradient_pos,
            &config.base_r, &config.base_g, &config.base_b,
            &config.low_r, &config.low_g, &config.low_b,
            &config.high_r, &config.high_g, &config.high_b,
            &config.gradient_speed);
        config.mode = 3;
        return;
    }
    
    int params = sscanf(data.c_str(), 
        "M%hhu;B%hhu,%hhu,%hhu;L%hhu,%hhu,%hhu,%f;H%hhu,%hhu,%hhu,%f;T%f",
        &config.mode,
        &config.base_r, &config.base_g, &config.base_b,
        &config.low_r, &config.low_g, &config.low_b, &config.low_level,
        &config.high_r, &config.high_g, &config.high_b, &config.high_level,
        &config.threshold);
}

void updateGradient() {
    unsigned long currentTime = millis();
    if (currentTime - lastGradientUpdate > (110 - config.gradient_speed)) {
        lastGradientUpdate = currentTime;
        
        for (int i = 0; i < NUM_LEDS; i++) {
            // Плавное смещение градиента по всей ленте
            float pos = fmod(config.gradient_pos + (float)i / NUM_LEDS, 1.0);
            
            // Плавное смешивание цветов по всей длине
            uint32_t color;
            if (pos < 0.5) {
                float t = pos * 2.0;
                color = interpolateColor(config.base_r, config.base_g, config.base_b,
                                       config.low_r, config.low_g, config.low_b, t);
            } else {
                float t = (pos - 0.5) * 2.0;
                color = interpolateColor(config.low_r, config.low_g, config.low_b,
                                       config.high_r, config.high_g, config.high_b, t);
            }
            
            strip.setPixelColor(i, color);
        }
        strip.show();
        
        // Автоматическое движение градиента
        config.gradient_pos = fmod(config.gradient_pos + 0.01, 1.0);
    }
}

uint32_t interpolateColor(uint8_t r1, uint8_t g1, uint8_t b1,
                         uint8_t r2, uint8_t g2, uint8_t b2, float t) {
    uint8_t r = r1 + (r2 - r1) * t;
    uint8_t g = g1 + (g2 - g1) * t;
    uint8_t b = b1 + (b2 - b1) * t;
    return strip.Color(r, g, b);
}

void updateLEDs() {
    if (config.mode == 3) return; // Градиент управляется отдельно
    
    strip.fill(strip.Color(config.base_r, config.base_g, config.base_b));
    
    if (config.mode == 0) {
        strip.show();
        return;
    }
    
    if (config.low_level > config.threshold) {
        uint32_t color = strip.Color(config.low_r, config.low_g, config.low_b);
        uint16_t count = map(config.low_level * 100, 0, 100, 0, NUM_LEDS/2);
        for (int i = 0; i < count; i++) {
            strip.setPixelColor(i, color);
        }
    }
    
    if (config.mode == 2 && config.high_level > config.threshold) {
        uint32_t color = strip.Color(config.high_r, config.high_g, config.high_b);
        uint16_t start = NUM_LEDS - map(config.high_level * 100, 0, 100, 0, NUM_LEDS/2);
        for (int i = start; i < NUM_LEDS; i++) {
            strip.setPixelColor(i, color);
        }
    }
    
    strip.show();
}
