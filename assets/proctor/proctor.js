const PROC_INTERVAL_MS = 400;
const FACE_API_MODELS = "./models";
const MEDIAPIPE_ROOT = "./vendor/mediapipe";
const CANDIDATE_LABEL = "candidate";
const DETECTION_TYPES = {
    IDLE: "Initializing",
    READY: "Ready",
    CAMERA: "Starting Camera",
    VERIFIED: "Face Verified",
    MULTIPLE_FACES: "Multiple Face Detected",
    FACE_NOT_VISIBLE: "Face Not Visible",
    FACE_MISMATCH: "Face Mismatch",
    ERROR: "Detection Error",
};

class ProctorState {
    constructor() {
        this.modelsLoaded = false;
        this.sessionStarted = false;
        this.referenceDescriptor = null;
        this.faceMeshResults = null;
        this.faceMatcher = null;
    }
}

class ProctorUI {
    constructor() {
        this.video = document.getElementById("videoElement");
        this.canvas = document.getElementById("canvasElement");
        this.ctx = this.canvas.getContext("2d");
        this.detectionBanner = document.getElementById("detectionBanner");
        this.detectionType = document.getElementById("detectionType");
        this.introScreen = document.getElementById("introScreen");
        this.btnStartSession = document.getElementById("btnStartSession");
    }

    setDetectionState(text, tone = "neutral", visible = true) {
        if (!this.detectionBanner || !this.detectionType) {
            return;
        }
        this.detectionType.innerText = text;
        this.detectionBanner.dataset.tone = tone;
        this.detectionBanner.classList.toggle("hidden", !visible);
    }

    setButtonState(label, disabled) {
        this.btnStartSession.innerText = label;
        this.btnStartSession.disabled = disabled;
    }

    hideIntro() {
        this.introScreen.classList.add("hidden");
    }
}

class ProctorClient {
    constructor() {
        this.state = new ProctorState();
        this.ui = new ProctorUI();
        this.faceMesh = null;
        this.bridge = null;
        this.isDragging = false;

        this.ui.btnStartSession.addEventListener("click", () => this.startSession());
    }

    async init() {
        try {
            await this.initBridge();
            await this.loadModels();
            this.state.modelsLoaded = true;
            this.ui.setButtonState("Enable Camera", false);
            this.ui.setDetectionState(DETECTION_TYPES.READY, "neutral", false);
        } catch (error) {
            this.ui.setButtonState("Unavailable", true);
            this.ui.setDetectionState(DETECTION_TYPES.ERROR, "danger");
            window.alert(`Unable to initialize proctoring: ${error.message}`);
        }
    }

    async initBridge() {
        if (!window.qt || !window.QWebChannel) {
            return;
        }

        await new Promise((resolve) => {
            new QWebChannel(window.qt.webChannelTransport, (channel) => {
                this.bridge = channel.objects.proctorBridge || null;
                resolve();
            });
        });

        this.bindDragHandlers();
    }

    bindDragHandlers() {
        if (!this.bridge) {
            return;
        }

        document.addEventListener("mousedown", (event) => {
            if (event.button !== 0) {
                return;
            }
            this.isDragging = true;
            if (typeof this.bridge.startDrag === "function") {
                this.bridge.startDrag(Math.round(event.screenX), Math.round(event.screenY));
            }
        });

        document.addEventListener("mousemove", (event) => {
            if (!this.isDragging) {
                return;
            }
            if (typeof this.bridge.dragTo === "function") {
                this.bridge.dragTo(Math.round(event.screenX), Math.round(event.screenY));
            }
        });

        const endDrag = () => {
            if (!this.isDragging) {
                return;
            }
            this.isDragging = false;
            if (typeof this.bridge.endDrag === "function") {
                this.bridge.endDrag();
            }
        };

        document.addEventListener("mouseup", endDrag);
        document.addEventListener("mouseleave", endDrag);
    }

    async loadModels() {
        await faceapi.nets.tinyFaceDetector.loadFromUri(FACE_API_MODELS);
        await faceapi.nets.faceLandmark68Net.loadFromUri(FACE_API_MODELS);
        await faceapi.nets.faceRecognitionNet.loadFromUri(FACE_API_MODELS);

        this.faceMesh = new FaceMesh({
            locateFile: (file) => `${MEDIAPIPE_ROOT}/${file}`,
        });
        this.faceMesh.setOptions({
            maxNumFaces: 1,
            refineLandmarks: true,
            minDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5,
        });
        this.faceMesh.onResults((results) => {
            this.state.faceMeshResults = results;
        });
    }

    async startSession() {
        if (!this.state.modelsLoaded || this.state.sessionStarted) {
            return;
        }

        this.ui.setButtonState("Starting...", true);
        this.ui.setDetectionState(DETECTION_TYPES.CAMERA, "neutral");

        try {
            await this.startWebcam();
            await this.captureReferenceFace();
            this.state.sessionStarted = true;
            this.ui.hideIntro();
            this.ui.setDetectionState(DETECTION_TYPES.VERIFIED, "success");
            this.startProcessing();
            if (this.bridge && typeof this.bridge.startSession === "function") {
                this.bridge.startSession();
            }
        } catch (error) {
            this.ui.setButtonState("Enable Camera", false);
            this.ui.setDetectionState(DETECTION_TYPES.ERROR, "danger");
            window.alert(error.message);
        }
    }

    async startWebcam() {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: 640,
                height: 480,
                facingMode: "user",
            },
            audio: false,
        });

        this.ui.video.srcObject = stream;
        await this.ui.video.play();

        await new Promise((resolve) => {
            const onMetadataLoaded = () => {
                this.ui.video.removeEventListener("loadedmetadata", onMetadataLoaded);
                resolve();
            };
            this.ui.video.addEventListener("loadedmetadata", onMetadataLoaded);
            if (this.ui.video.readyState >= 1) {
                onMetadataLoaded();
            }
        });

        this.ui.canvas.width = this.ui.video.videoWidth;
        this.ui.canvas.height = this.ui.video.videoHeight;
    }

    async captureReferenceFace() {
        let detection = null;

        for (let attempt = 0; attempt < 8; attempt += 1) {
            detection = await faceapi
                .detectSingleFace(this.ui.video, new faceapi.TinyFaceDetectorOptions())
                .withFaceLandmarks()
                .withFaceDescriptor();

            if (detection) {
                break;
            }

            await new Promise((resolve) => window.setTimeout(resolve, 180));
        }

        if (!detection) {
            throw new Error("No clear face detected. Look at the camera and try again.");
        }

        this.state.referenceDescriptor = detection.descriptor;
        this.state.faceMatcher = new faceapi.FaceMatcher([
            new faceapi.LabeledFaceDescriptors(CANDIDATE_LABEL, [detection.descriptor]),
        ], 0.55);
    }

    startProcessing() {
        window.setTimeout(() => this.processLoop(), PROC_INTERVAL_MS);
    }

    drawLabel(box, color) {
        this.ui.ctx.fillStyle = color;
        this.ui.ctx.font = "600 15px Segoe UI";
        this.ui.ctx.fillText(CANDIDATE_LABEL, box.x, Math.max(18, box.y - 8));
    }

    async processLoop() {
        if (!this.state.sessionStarted) {
            return;
        }

        const options = new faceapi.TinyFaceDetectorOptions({
            inputSize: 320,
            scoreThreshold: 0.5,
        });

        const detections = await faceapi
            .detectAllFaces(this.ui.video, options)
            .withFaceLandmarks()
            .withFaceDescriptors();

        await this.faceMesh.send({ image: this.ui.video });

        this.ui.ctx.clearRect(0, 0, this.ui.canvas.width, this.ui.canvas.height);
        this.drawFaceBox(detections);

        window.setTimeout(() => this.processLoop(), PROC_INTERVAL_MS);
    }

    drawFaceBox(detections) {
        if (detections.length === 0) {
            this.ui.setDetectionState(DETECTION_TYPES.FACE_NOT_VISIBLE, "danger");
            return;
        }

        if (detections.length > 1) {
            this.ui.setDetectionState(DETECTION_TYPES.MULTIPLE_FACES, "danger");
        }

        const detection = detections[0];
        const match = this.state.faceMatcher.findBestMatch(detection.descriptor);
        const box = detection.detection.box;
        const isVerified = match.label !== "unknown";
        const color = isVerified ? "#36d37a" : "#ef4444";

        this.ui.ctx.strokeStyle = color;
        this.ui.ctx.lineWidth = 2;
        this.ui.ctx.strokeRect(box.x, box.y, box.width, box.height);
        this.drawLabel(box, color);
        if (detections.length === 1) {
            this.ui.setDetectionState(
                isVerified ? DETECTION_TYPES.VERIFIED : DETECTION_TYPES.FACE_MISMATCH,
                isVerified ? "success" : "danger",
            );
        }
    }
}

window.addEventListener("load", () => {
    const client = new ProctorClient();
    client.init();
});
