plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.robofleet.temibridge"
    compileSdk {
        version = release(36)
    }

    defaultConfig {
        applicationId = "com.robofleet.temibridge"
        minSdk = 23
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    kotlinOptions {
        jvmTarget = "11"
    }
    buildFeatures {
        compose = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.7.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.cardview:cardview:1.0.0")
// Temi SDK
    implementation("com.robotemi:sdk:1.136.0")
// WebSocket Server - NanoHTTPD with WebSocket support
    implementation("org.nanohttpd:nanohttpd:2.3.1")
    implementation("org.nanohttpd:nanohttpd-websocket:2.3.1")
// HTTP Client for FastAPI communication
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
// JSON parsing
    implementation("com.google.code.gson:gson:2.10.1")
// Coroutines for async operations
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
// Lifecycle
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-service:2.7.0")

    // Compose dependencies
    implementation("androidx.compose.ui:ui:1.5.2")
    implementation("androidx.compose.material3:material3:1.3.2")
    implementation("androidx.compose.ui:ui-tooling-preview:1.5.2")
    debugImplementation("androidx.compose.ui:ui-tooling:1.5.2")
    implementation("androidx.activity:activity-compose:1.8.2")

    // -----------------------
    // Testing dependencies
    // -----------------------
    testImplementation("junit:junit:4.13.2") // Unit tests
    androidTestImplementation("androidx.test.ext:junit:1.1.5") // AndroidJUnit4
    androidTestImplementation ("androidx.test.espresso:espresso-core:3.5.1")
    androidTestImplementation("androidx.test:core:1.6.0")
    androidTestImplementation("androidx.test:runner:1.6.1")
    androidTestImplementation("androidx.test:rules:1.6.1")
}