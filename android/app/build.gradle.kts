import java.io.File
import java.security.KeyStore
import java.security.cert.X509Certificate
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

/**
 * The version comes from the repository's VERSION file, the same one the
 * desktop installer and the app's own footer read. One file to bump, and the
 * two apps can never claim different versions of the same release.
 */
val appVersion: String =
    rootProject.file("../VERSION").takeIf { it.exists() }?.readText()?.trim() ?: "0.0.0"

/** versionCode must be an increasing integer: 1.2.3 -> 10203. */
val appVersionCode: Int = appVersion.split(".").let { parts ->
    val major = parts.getOrNull(0)?.toIntOrNull() ?: 0
    val minor = parts.getOrNull(1)?.toIntOrNull() ?: 0
    val patch = parts.getOrNull(2)?.toIntOrNull() ?: 0
    major * 10000 + minor * 100 + patch
}.coerceAtLeast(1)

/**
 * Release signing, for the Play Store bundle.
 *
 * The upload key never enters this repository. It is read from
 * `android/keystore.properties` on a developer machine (gitignored, see
 * keystore.properties.example) or from environment variables in CI, where the
 * keystore itself arrives base64-encoded in a secret. Either source is
 * optional: without one, `assembleDebug` still works exactly as before, which
 * is what every technician build and every pull request needs.
 *
 * Losing this key is recoverable, but only because Play App Signing holds the
 * real distribution key and Google can reset an upload key. Back it up anyway.
 */
val keystoreProperties: Properties = Properties().apply {
    rootProject.file("keystore.properties")
        .takeIf { it.exists() }
        ?.inputStream()
        ?.use { load(it) }
}

fun signingSecret(property: String, environmentVariable: String): String? =
    (keystoreProperties.getProperty(property) ?: System.getenv(environmentVariable))
        ?.takeIf { it.isNotBlank() }

/** Relative paths resolve against `android/`, so the keystore and its properties file can move as a pair. */
val keystoreFile: File? =
    signingSecret("storeFile", "HEXR_KEYSTORE_FILE")
        ?.let { path -> File(path).takeIf { it.isAbsolute } ?: rootProject.file(path) }
        ?.takeIf { it.exists() }

android {
    namespace = "com.microtube.hexr"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.microtube.hexr.tester"
        // Android 8.0. BLE works further back, but the runtime-permission and
        // GATT behaviour below this is different enough to need its own testing,
        // and no HEXR customer is on it.
        minSdk = 26
        // Android 16. Play's floor for a new submission moved here on 31 August
        // 2026, and it moves again roughly every August. The app was already
        // edge-to-edge and declares no orientation lock, which is what that bump
        // usually breaks.
        targetSdk = 36
        versionCode = appVersionCode
        versionName = appVersion

        // The commit this APK came from, shown on the Connect screen. Without
        // it there is no way to tell two sideloaded builds apart on a phone,
        // and a bug report against "the app" cannot be pinned to a version.
        resValue(
            "string",
            "build_sha",
            System.getenv("GITHUB_SHA")?.take(7) ?: "local",
        )
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        // Created only when a key is actually available, so a checkout with no
        // keystore still configures. `bundleRelease` fails loudly below rather
        // than quietly producing an unsigned bundle Play would reject anyway.
        if (keystoreFile != null) {
            create("release") {
                storeFile = keystoreFile
                storePassword = signingSecret("storePassword", "HEXR_KEYSTORE_PASSWORD")
                keyAlias = signingSecret("keyAlias", "HEXR_KEY_ALIAS")
                keyPassword = signingSecret("keyPassword", "HEXR_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            // The sideloaded build and the Play build are the same application
            // signed with different keys, and Android will not swap one for the
            // other in place. Giving the technician build its own identity lets
            // both sit on one phone instead of trading uninstalls.
            applicationIdSuffix = ".debug"
        }

        release {
            // Left unminified deliberately. The APK size is irrelevant next to
            // a readable stack trace from a technician's phone, and R8 rules
            // that have never been exercised at runtime are their own risk on
            // the build that goes to customers.
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("release")
        }
    }

    // The app ships one language and no per-locale resources. Splitting the
    // bundle by language buys nothing and adds a way for a device to end up
    // installed without its strings, so it is off.
    bundle {
        language {
            enableSplit = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)

    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")

    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")

    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.compose.ui:ui-tooling-preview")

    testImplementation("junit:junit:4.13.2")
    // Unit tests run on the JVM against a stubbed android.jar, whose org.json throws "not mocked".
    // The real library stands in for it there; the app itself uses the copy built into Android.
    testImplementation("org.json:json:20240303")
}

/**
 * Play refuses a bundle whose signing certificate expires before 22 October
 * 2033 — "signed with a certificate that expires too soon". The trap is that
 * `keytool -genkeypair` defaults to a 90-day certificate when `-validity` is
 * missing, and it is easy to lose that flag: a throwaway key made to prove the
 * release build works, or the documented command pasted into a shell that does
 * not join its backslash line continuations. Nothing downstream notices —
 * Gradle signs the bundle, the upload takes half an hour, and the Console
 * rejects it.
 */
val playCertificateFloor: Instant = LocalDate.of(2033, 10, 22).atStartOfDay(ZoneOffset.UTC).toInstant()

/**
 * The certificate the release build would sign with, or null if it cannot be
 * read. A wrong password or a missing alias is the signing config's failure to
 * report, not this check's, so those stay silent here.
 */
fun releaseCertificate(): X509Certificate? {
    val store = keystoreFile ?: return null
    val password = signingSecret("storePassword", "HEXR_KEYSTORE_PASSWORD") ?: return null
    val alias = signingSecret("keyAlias", "HEXR_KEY_ALIAS") ?: return null
    val certificate = try {
        KeyStore.getInstance(store, password.toCharArray()).getCertificate(alias)
    } catch (e: Exception) {
        null
    }
    return certificate as? X509Certificate
}

/**
 * An unsigned release bundle is not a build failure to AGP — it just writes the
 * file and moves on, and you find out when the Play Console rejects it half an
 * hour later. Catch it at configuration time instead, with the fix in the
 * message. Same for a certificate that will not outlive Play's floor.
 */
gradle.taskGraph.whenReady {
    val buildingRelease = allTasks.any { it.name in setOf("bundleRelease", "assembleRelease") }
    if (!buildingRelease) return@whenReady

    val store = keystoreFile
    if (store == null) {
        throw GradleException(
            "No release signing key. Create android/keystore.properties from " +
                "keystore.properties.example (or set HEXR_KEYSTORE_FILE, " +
                "HEXR_KEYSTORE_PASSWORD, HEXR_KEY_ALIAS and HEXR_KEY_PASSWORD). " +
                "See android/PLAY-RELEASE.md.",
        )
    }

    val expiry = releaseCertificate()?.notAfter?.toInstant()
    if (expiry != null && expiry.isBefore(playCertificateFloor)) {
        val readable = DateTimeFormatter.ofPattern("d MMMM uuuu").withZone(ZoneOffset.UTC)
        throw GradleException(
            """
            |The signing key in ${store.name} expires on ${readable.format(expiry)}.
            |Google Play requires a certificate valid until at least 22 October 2033, and will
            |reject the upload. Generate a real upload key, with an explicit validity:
            |
            |  keytool -genkeypair -v -keystore hexr-upload.jks -alias hexr-upload -keyalg RSA -keysize 4096 -validity 10000 -dname "CN=Microtube, O=Microtube, C=GB"
            |
            |See android/PLAY-RELEASE.md.
            """.trimMargin(),
        )
    }
}
