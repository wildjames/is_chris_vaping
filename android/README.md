# IsChrisVaping Android App

BLE companion app for the IsChrisVaping vape sensor.

## CI/CD — Firebase App Distribution

Pushes to `main` that modify files under `android/` trigger the GitHub Actions workflow (`.github/workflows/android.yml`), which builds a signed release APK and uploads it to Firebase App Distribution for beta testers.

### Setup

#### 1. Firebase Project

1. Create a project at [Firebase Console](https://console.firebase.google.com/)
2. Add an Android app with package name `com.ischrisvaping.app`
3. Note the **App ID** (e.g. `1:123456789:android:abcdef`)

#### 2. Service Account

1. In Firebase Console → **Project Settings** → **Service accounts**
2. Click **Generate new private key** — downloads a JSON file
3. Copy the entire JSON contents for use as a GitHub secret

#### 3. Tester Group

1. In Firebase Console → **App Distribution** → **Testers & Groups**
2. Create a group named exactly **`beta-testers`**
3. Add beta tester email addresses

#### 4. Signing Keystore

Generate a release keystore (using OpenSSL, since `keytool` can hang in WSL):

```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 10000 -nodes \
  -subj "/CN=Is Chris Vaping/O=IsChrisVaping/L=London/C=GB"
openssl pkcs12 -export -in cert.pem -inkey key.pem -out release.keystore \
  -name is_chris_vaping -passout pass:YOUR_PASSWORD
rm key.pem cert.pem
```

Then base64-encode it:

```bash
base64 -w 0 release.keystore
```

#### 5. GitHub Secrets

Add these in the repo under **Settings → Secrets and variables → Actions**:

| Secret | Value |
|--------|-------|
| `FIREBASE_APP_ID` | Firebase App ID from step 1 |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Full JSON from step 2 |
| `ANDROID_KEYSTORE_BASE64` | Base64-encoded keystore from step 4 |
| `ANDROID_KEYSTORE_PASSWORD` | Password used when creating the keystore |
| `ANDROID_KEY_ALIAS` | `is_chris_vaping` |
| `ANDROID_KEY_PASSWORD` | Same as keystore password |

### How it works

1. Workflow decodes the base64 keystore to a file
2. Gradle builds a signed release APK using env vars for signing config
3. APK is uploaded as a GitHub Actions artifact
4. APK is distributed to the `beta-testers` group via Firebase App Distribution
5. Testers receive an email invite to install the latest build

### Local development

```bash
cd android
./gradlew assembleDebug
```
