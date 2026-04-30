# SecureExamBrowser

## Features

- Launches a locked-down exam browser window with a configurable start URL.
- Quits the App, on visting end exam link
- Enforces kiosk-style system guard behavior during the exam session.
- Monitors internet connectivity throughout the session.
- Integrated Wi-Fi management so that candidate don't have to quit the app for internet switch/connectivity
- Terminates deny-listed remote desktop (e.g. AnyDesk, TeamViewer, etc) and remote support apps (Whatsapp, Slack etc) automatically.
- Detects suspicious remote-access connections by known domains and ports (App will kill the process even if Candidate renames the executable such as `anydesk.exe` to `test.exe`)
- Detect Multiple Screens
- AI Web Cam Proctoring
    - Multiple Face Detection
    - Face Verification throughout the session
    - No Face Detection
- Auto Exit App, If Duration of exam is 75 min, then after the start time of exam, exactly after 75 min, app will auto close
- Virtual Machine detection (Student cannot boot the software in a VM, which can bypass all OS hooks)
- Shows Current Datetime & Battery Percentage in Tool Bar
- Second-instance prevention (Running two copies of the browser)

## TODO

- [ ] Screen recording detection (OBS/QuickTime captures without using Print Screen)
- [ ] Clipboard monitoring (Paste-from-phone via cloud clipboard)
- [ ] USB device detection (Phone-as-keyboard, external storage)
- [ ] Anti-Software Cracking Strategies

## Ways to Quit Exam

- Redirect Candidate to `seb://quit`
- Using `Quit Exam` Password (Ideally only supervisor should enter it)
- `Auto Exit` the app exactly when the exam duration ends (e.g., 75 minutes after the start time) 

## Installation

- `Windows`: download [SecureExamBrowser.exe](https://github.com/PushpenderIndia/SecureExamBrowser/releases/latest/download/SecureExamBrowser.exe) and run it.

- `Linux`: download [SecureExamBrowser-linux](https://github.com/PushpenderIndia/SecureExamBrowser/releases/latest/download/SecureExamBrowser-linux), run `chmod +x SecureExamBrowser-linux`, then start it.

- `macOS (Apple Silicon)`: 
    - Download [SecureExamBrowser-macos-arm64.zip](https://github.com/PushpenderIndia/SecureExamBrowser/releases/latest/download/SecureExamBrowser-macos-arm64.zip)
    - Unzip it
    - Run `xattr -dr com.apple.quarantine SecureExamBrowser.app` before opening it because the app is not signed.

- `macOS (Intel)`: 
    - Download [SecureExamBrowser-macos-intel.zip](https://github.com/PushpenderIndia/SecureExamBrowser/releases/latest/download/SecureExamBrowser-macos-intel.zip)
    - Unzip it
    - Run `xattr -dr com.apple.quarantine SecureExamBrowser.app` before opening it because the app is not signed.

## Screenshots

### 1. App Start Screen

![App Start Screen](docs/start_screen.png)

### 2. Web Cam Advisory Modal

![Web Cam Advisory Modal](docs/webcam_advisory_modal.png)

### 3. Web Cam Onboarding

![Web Cam Onboarding](docs/webcam_onboarding.png)

### 4. SecureExamBrowser opens your start exam with AI Web Cam Proctor

![Cam Proctor - 1](docs/moveable_ai_cam_proctor_1.png)

### 5. User can switch to another WiFi from the SEB itself

![Change WiFi](docs/change_wifi.png)

### 6. Quit Exam using Admin Password 

![Quit Exam](docs/quit_exam.png)

### 7. Moveable AI Web Cam Proctor 

![Cam Proctor - 2](docs/moveable_ai_cam_proctor_2.png)
