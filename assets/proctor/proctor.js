const PROC_INTERVAL_MS = 400;
const FACE_API_MODELS = "./models";
const MEDIAPIPE_ROOT = "./vendor/mediapipe";
const CANDIDATE_LABEL = "candidate";
const FACE_MATCH_THRESHOLD = 0.6;
const CAPTURE_STEPS = [
    {
        label: "Front View",
        title: "Capture Front View",
        copy: "Look straight into the camera and capture a clear front-facing image.",
    },
    {
        label: "Left View",
        title: "Capture Left View",
        copy: "Turn slightly to your left so your left profile is visible, then capture the image.",
    },
    {
        label: "Right View",
        title: "Capture Right View",
        copy: "Turn slightly to your right so your right profile is visible, then capture the image.",
    },
];
const DETECTION_TYPES = {
    IDLE: "Initializing",
    READY: "Ready",
    CAMERA: "Starting Camera",
    FACE_MATCHED: "Face Matched",
    MULTIPLE_FACES: "Multiple Face Detected",
    FACE_NOT_VISIBLE: "Face Not Visible",
    FACE_NOT_DETECTED: "Face Not Detected",
    ERROR: "Detection Error",
};

class ProctorState {
    constructor() {
        this.modelsLoaded = false;
        this.cameraStarted = false;
        this.sessionStarted = false;
        this.enrollmentStepIndex = 0;
        this.enrollmentCaptures = CAPTURE_STEPS.map(() => null);
        this.pendingCapture = null;
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
        this.captureStepEyebrow = document.getElementById("captureStepEyebrow");
        this.captureStepTitle = document.getElementById("captureStepTitle");
        this.captureStepCopy = document.getElementById("captureStepCopy");
        this.capturedPreview = document.getElementById("capturedPreview");
        this.captureSuccessState = document.getElementById("captureSuccessState");
        this.btnStartCamera = document.getElementById("btnStartCamera");
        this.btnCaptureView = document.getElementById("btnCaptureView");
        this.btnConfirmView = document.getElementById("btnConfirmView");
        this.btnRecaptureView = document.getElementById("btnRecaptureView");
        this.captureSteps = Array.from(document.querySelectorAll(".capture-step"));
        this.captureStepThumbs = this.captureSteps.map((step) => step.querySelector(".capture-step-thumb"));
        this.captureStepStatuses = this.captureSteps.map((step) => step.querySelector(".capture-step-status"));
    }

    setDetectionState(text, tone = "neutral", visible = true) {
        if (!this.detectionBanner || !this.detectionType) {
            return;
        }
        this.detectionType.innerText = text;
        this.detectionBanner.dataset.tone = tone;
        this.detectionBanner.classList.toggle("hidden", !visible);
    }

    setPrimaryButtonState(label, disabled) {
        this.btnStartCamera.innerText = label;
        this.btnStartCamera.disabled = disabled;
    }

    setButtonVisibility({ startCamera, capture, confirm, retry }) {
        this.btnStartCamera.classList.toggle("hidden-action", !startCamera);
        this.btnCaptureView.classList.toggle("hidden-action", !capture);
        this.btnConfirmView.classList.toggle("hidden-action", !confirm);
        this.btnRecaptureView.classList.toggle("hidden-action", !retry);
    }

    hideIntro() {
        document.body.classList.add("session-live");
        this.introScreen.classList.add("hidden");
    }

    showPreview(imageSrc) {
        this.capturedPreview.src = imageSrc;
        this.capturedPreview.classList.remove("hidden");
    }

    showPlaceholder(text) {
        this.capturedPreview.classList.add("hidden");
        this.capturedPreview.removeAttribute("src");
    }

    showCaptureReady(show) {
        this.captureSuccessState.classList.toggle("hidden", !show);
    }

    updateCaptureStep(stepIndex, activeStepIndex, capture, isPendingPreview) {
        this.captureSteps.forEach((step, index) => {
            const hasConfirmedCapture = Boolean(capture);
            const status = this.captureStepStatuses[index];
            step.classList.toggle("is-active", index === activeStepIndex);
            step.classList.toggle("is-complete", hasConfirmedCapture);
            if (status) {
                if (hasConfirmedCapture) {
                    status.innerText = "Confirmed";
                } else if (index === activeStepIndex && isPendingPreview) {
                    status.innerText = "Ready";
                } else if (index === activeStepIndex) {
                    status.innerText = "Active";
                } else {
                    status.innerText = "Pending";
                }
            }
        });
    }

    updateThumbnail(stepIndex, imageSrc) {
        const thumb = this.captureStepThumbs[stepIndex];
        if (!thumb) {
            return;
        }
        if (imageSrc) {
            thumb.src = imageSrc;
            thumb.classList.remove("hidden");
            this.captureSteps[stepIndex].classList.add("is-complete");
            return;
        }
        thumb.removeAttribute("src");
        thumb.classList.add("hidden");
        this.captureSteps[stepIndex].classList.remove("is-complete");
    }
}

class ProctorClient {
    constructor() {
        this.state = new ProctorState();
        this.ui = new ProctorUI();
        this.faceMesh = null;
        this.bridge = null;
        this.isDragging = false;

        this.ui.btnStartCamera.addEventListener("click", () => this.startCamera());
        this.ui.btnCaptureView.addEventListener("click", () => this.captureCurrentView());
        this.ui.btnConfirmView.addEventListener("click", () => this.confirmCurrentCapture());
        this.ui.btnRecaptureView.addEventListener("click", () => this.recaptureCurrentStep());
        this.ui.captureSteps.forEach((step) => {
            step.addEventListener("click", () => {
                const stepIndex = Number(step.dataset.stepIndex);
                this.selectEnrollmentStep(stepIndex);
            });
        });
    }

    async init() {
        try {
            await this.initBridge();
            await this.loadModels();
            this.state.modelsLoaded = true;
            this.ui.setPrimaryButtonState("Enable Camera", false);
            this.syncEnrollmentUi();
            this.ui.setDetectionState(DETECTION_TYPES.READY, "neutral", false);
        } catch (error) {
            this.ui.setPrimaryButtonState("Unavailable", true);
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
            if (!this.state.sessionStarted || event.target.closest("button")) {
                return;
            }
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
            maxNumFaces: 3,
            refineLandmarks: true,
            minDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5,
        });
        this.faceMesh.onResults((results) => {
            this.state.faceMeshResults = results;
        });
    }

    syncEnrollmentUi() {
        const step = CAPTURE_STEPS[this.state.enrollmentStepIndex];
        const existingCapture = this.state.pendingCapture || this.state.enrollmentCaptures[this.state.enrollmentStepIndex];
        const confirmedCount = this.state.enrollmentCaptures.filter(Boolean).length;
        const hasPendingPreview = Boolean(this.state.pendingCapture);

        this.ui.captureStepEyebrow.innerText = `Step ${this.state.enrollmentStepIndex + 1} of ${CAPTURE_STEPS.length}`;
        this.ui.captureStepTitle.innerText = step.title;
        this.ui.captureStepCopy.innerText = step.copy;
        this.ui.captureSteps.forEach((_, index) => {
            this.ui.updateCaptureStep(index, this.state.enrollmentStepIndex, this.state.enrollmentCaptures[index], hasPendingPreview);
            this.ui.updateThumbnail(index, this.state.enrollmentCaptures[index]?.imageSrc || "");
        });

        if (existingCapture) {
            this.ui.showPreview(existingCapture.imageSrc);
            this.ui.showCaptureReady(hasPendingPreview);
        } else {
            this.ui.showPlaceholder("Live camera stays visible behind this panel. Capture a view, confirm it if it looks right, or retry it clearly.");
            this.ui.showCaptureReady(false);
        }

        this.ui.btnCaptureView.disabled = !this.state.cameraStarted;
        this.ui.btnConfirmView.disabled = !this.state.pendingCapture;
        this.ui.btnRecaptureView.disabled = !this.state.pendingCapture;

        if (!this.state.cameraStarted) {
            this.ui.setButtonVisibility({
                startCamera: true,
                capture: false,
                confirm: false,
                retry: false,
            });
        } else if (this.state.pendingCapture) {
            this.ui.setButtonVisibility({
                startCamera: false,
                capture: false,
                confirm: true,
                retry: true,
            });
        } else {
            this.ui.setButtonVisibility({
                startCamera: false,
                capture: true,
                confirm: false,
                retry: false,
            });
        }

        if (!this.state.cameraStarted) {
            this.ui.setPrimaryButtonState("Enable Camera", !this.state.modelsLoaded);
        } else if (confirmedCount === CAPTURE_STEPS.length && !this.state.pendingCapture) {
            this.ui.setPrimaryButtonState("All Views Captured", true);
        } else {
            this.ui.setPrimaryButtonState("Camera Enabled", true);
        }
    }

    async startCamera() {
        if (!this.state.modelsLoaded || this.state.cameraStarted) {
            return;
        }

        this.ui.setPrimaryButtonState("Starting...", true);
        this.ui.setDetectionState(DETECTION_TYPES.CAMERA, "neutral");

        try {
            await this.startWebcam();
            this.state.cameraStarted = true;
            this.syncEnrollmentUi();
        } catch (error) {
            this.ui.setPrimaryButtonState("Enable Camera", false);
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

    async ensureSingleFaceVisible() {
        await this.faceMesh.send({ image: this.ui.video });
        const faces = this.getDetectedFaces();
        if (faces.length === 0) {
            this.ui.setDetectionState(DETECTION_TYPES.FACE_NOT_VISIBLE, "danger");
            throw new Error("Face not visible. Align your face and try again.");
        }
        if (faces.length > 1) {
            this.ui.setDetectionState(DETECTION_TYPES.MULTIPLE_FACES, "danger");
            throw new Error("Multiple faces detected. Ensure only one face is visible.");
        }
    }

    captureImage() {
        const captureCanvas = document.createElement("canvas");
        captureCanvas.width = this.ui.video.videoWidth;
        captureCanvas.height = this.ui.video.videoHeight;
        const captureCtx = captureCanvas.getContext("2d");
        captureCtx.drawImage(this.ui.video, 0, 0, captureCanvas.width, captureCanvas.height);
        return captureCanvas.toDataURL("image/jpeg", 0.92);
    }

    async captureCurrentView() {
        if (!this.state.cameraStarted || this.state.sessionStarted) {
            return;
        }

        try {
            await this.ensureSingleFaceVisible();
            const detection = await faceapi
                .detectSingleFace(this.ui.video, new faceapi.TinyFaceDetectorOptions({
                    inputSize: 320,
                    scoreThreshold: 0.5,
                }))
                .withFaceLandmarks()
                .withFaceDescriptor();

            if (!detection) {
                this.ui.setDetectionState(DETECTION_TYPES.FACE_NOT_VISIBLE, "danger");
                throw new Error("Face not visible. Align your face and try again.");
            }

            this.state.pendingCapture = {
                descriptor: detection.descriptor,
                imageSrc: this.captureImage(),
            };
            this.ui.setDetectionState(DETECTION_TYPES.READY, "neutral", false);
            this.syncEnrollmentUi();
        } catch (error) {
            window.alert(error.message);
        }
    }

    selectEnrollmentStep(stepIndex) {
        if (Number.isNaN(stepIndex) || stepIndex < 0 || stepIndex >= CAPTURE_STEPS.length) {
            return;
        }
        this.state.enrollmentStepIndex = stepIndex;
        this.state.pendingCapture = null;
        this.syncEnrollmentUi();
    }

    recaptureCurrentStep() {
        if (!this.state.cameraStarted) {
            return;
        }
        this.state.pendingCapture = null;
        this.syncEnrollmentUi();
    }

    async confirmCurrentCapture() {
        if (!this.state.pendingCapture) {
            return;
        }

        this.state.enrollmentCaptures[this.state.enrollmentStepIndex] = this.state.pendingCapture;
        this.state.pendingCapture = null;

        const nextPendingIndex = this.state.enrollmentCaptures.findIndex((capture) => !capture);
        if (nextPendingIndex === -1) {
            await this.completeEnrollment();
            return;
        }

        this.state.enrollmentStepIndex = nextPendingIndex;
        this.syncEnrollmentUi();
    }

    async completeEnrollment() {
        const descriptors = this.state.enrollmentCaptures
            .filter(Boolean)
            .map((capture) => capture.descriptor);

        if (descriptors.length !== CAPTURE_STEPS.length) {
            return;
        }

        this.state.faceMatcher = new faceapi.FaceMatcher([
            new faceapi.LabeledFaceDescriptors(CANDIDATE_LABEL, descriptors),
        ], FACE_MATCH_THRESHOLD);
        this.state.sessionStarted = true;
        this.ui.hideIntro();
        this.ui.setDetectionState(DETECTION_TYPES.FACE_MATCHED, "success");
        this.startProcessing();
        if (this.bridge && typeof this.bridge.startSession === "function") {
            this.bridge.startSession();
        }
    }

    startProcessing() {
        window.setTimeout(() => this.processLoop(), PROC_INTERVAL_MS);
    }

    getDetectedFaces() {
        return this.state.faceMeshResults?.multiFaceLandmarks || [];
    }

    getFaceBoxFromLandmarks(landmarks) {
        let minX = 1;
        let minY = 1;
        let maxX = 0;
        let maxY = 0;

        landmarks.forEach((point) => {
            minX = Math.min(minX, point.x);
            minY = Math.min(minY, point.y);
            maxX = Math.max(maxX, point.x);
            maxY = Math.max(maxY, point.y);
        });

        const padding = 0.04;
        const x = Math.max(0, (minX - padding) * this.ui.canvas.width);
        const y = Math.max(0, (minY - padding) * this.ui.canvas.height);
        const right = Math.min(1, maxX + padding) * this.ui.canvas.width;
        const bottom = Math.min(1, maxY + padding) * this.ui.canvas.height;

        return {
            x,
            y,
            width: Math.max(0, right - x),
            height: Math.max(0, bottom - y),
        };
    }

    async getIdentityMatch() {
        const detection = await faceapi
            .detectSingleFace(this.ui.video, new faceapi.TinyFaceDetectorOptions({
                inputSize: 320,
                scoreThreshold: 0.5,
            }))
            .withFaceLandmarks()
            .withFaceDescriptor();

        if (!detection) {
            return null;
        }

        return this.state.faceMatcher.findBestMatch(detection.descriptor);
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

        await this.faceMesh.send({ image: this.ui.video });

        this.ui.ctx.clearRect(0, 0, this.ui.canvas.width, this.ui.canvas.height);
        await this.drawFaceBox();

        window.setTimeout(() => this.processLoop(), PROC_INTERVAL_MS);
    }

    async drawFaceBox() {
        const faces = this.getDetectedFaces();

        if (faces.length === 0) {
            this.ui.setDetectionState(DETECTION_TYPES.FACE_NOT_VISIBLE, "danger");
            return;
        }

        if (faces.length > 1) {
            this.ui.setDetectionState(DETECTION_TYPES.MULTIPLE_FACES, "danger");
            faces.forEach((landmarks) => {
                const box = this.getFaceBoxFromLandmarks(landmarks);
                this.ui.ctx.strokeStyle = "#ef4444";
                this.ui.ctx.lineWidth = 2;
                this.ui.ctx.strokeRect(box.x, box.y, box.width, box.height);
            });
            return;
        }

        const box = this.getFaceBoxFromLandmarks(faces[0]);
        const match = await this.getIdentityMatch();
        const isVerified = match && match.label !== "unknown";
        const color = isVerified ? "#36d37a" : "#ef4444";

        this.ui.ctx.strokeStyle = color;
        this.ui.ctx.lineWidth = 2;
        this.ui.ctx.strokeRect(box.x, box.y, box.width, box.height);
        this.drawLabel(box, color);
        this.ui.setDetectionState(
            isVerified ? DETECTION_TYPES.FACE_MATCHED : DETECTION_TYPES.FACE_NOT_DETECTED,
            isVerified ? "success" : "danger",
        );
    }
}

window.addEventListener("load", () => {
    const client = new ProctorClient();
    client.init();
});
