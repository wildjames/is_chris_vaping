plugins {
    id("com.android.application")
    // Add the Google services Gradle plugin
    id("com.google.gms.google-services")
}

// Version injected at build time via APP_VERSION env var (same logic as firmware).
// Without it the app reports "0.0.0" / versionCode 1.
val appVersion: String = System.getenv("APP_VERSION") ?: "0.0.0"
val appVersionCode: Int = run {
    val parts = appVersion.split(".")
    if (parts.size == 3) {
        val (major, minor, patch) = parts.map { it.toIntOrNull() ?: 0 }
        major * 10000 + minor * 100 + patch
    } else {
        1
    }
}

android {
    namespace = "com.ischrisvaping.app"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.ischrisvaping.app"
        minSdk = 33
        targetSdk = 37
        versionCode = appVersionCode
        versionName = appVersion
    }

    signingConfigs {
        create("release") {
            val keystoreFile = System.getenv("KEYSTORE_FILE")
            if (keystoreFile != null) {
                storeFile = file(keystoreFile)
                storePassword = System.getenv("KEYSTORE_PASSWORD")
                keyAlias = System.getenv("KEY_ALIAS")
                keyPassword = System.getenv("KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.19.0")
    implementation("androidx.appcompat:appcompat:1.7.1")
    implementation("com.google.android.material:material:1.14.0")
    implementation("androidx.constraintlayout:constraintlayout:2.2.1")
    implementation("androidx.recyclerview:recyclerview:1.4.0")
    implementation("no.nordicsemi.android:dfu:2.4.2")

    // Import the Firebase BoM
    implementation(platform("com.google.firebase:firebase-bom:34.16.0"))
    implementation("com.google.firebase:firebase-analytics")
    implementation("com.google.firebase:firebase-messaging")
}
