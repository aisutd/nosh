import { useRef, useState } from "react";
import { Alert, StyleSheet, View, Button, Linking } from "react-native";
import { SafeAreaProvider, SafeAreaView, } from "react-native-safe-area-context";
import { WebView } from "react-native-webview";
import * as ImagePicker from "expo-image-picker";
import { File } from "expo-file-system";
import { fetch as expoFetch } from "expo/fetch";
import { CameraView, useCameraPermissions } from "expo-camera";
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
} from "expo-audio";
import * as Speech from "expo-speech";

// Network endpoints for web app and backend API
const HOST = "192.168.1.6";
const APP_URL = `http://${HOST}:5173`;
const API = `http://${HOST}:8000`;

export default function App() {
  const webRef = useRef(null);
  const cameraRef = useRef(null);

  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const [videoMode, setVideoMode] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [videoToken, setVideoToken] = useState("");
  const [cameraReady, setCameraReady] = useState(false);

  function notifyScanStatus(scanning) {
    webRef.current?.injectJavaScript(`
      window.dispatchEvent(new CustomEvent("nosh-scan-status", {
        detail: { scanning: ${JSON.stringify(scanning)} }
      }));
      true;
    `);
  }
  // Take a fridge photo and send it to the backend.
  async function scanWithCamera(token) {
    const perm = await ImagePicker.requestCameraPermissionsAsync();

    if (!perm.granted) {
      Alert.alert("Camera permission is needed to scan your fridge.");
      return;
    }

    const result = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (result.canceled) return;

    const photo = result.assets[0];

    try {
      notifyScanStatus(true);
      const form = new FormData();
      form.append("image", new File(photo.uri));

      const response = await fetch(`${API}/scan`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });

      if (!response.ok) {
        throw new Error(`Server said ${response.status}`);
      }

      const data = await response.json();

      webRef.current?.injectJavaScript(
        `window.dispatchEvent(new CustomEvent("nosh-scan", {
          detail: ${JSON.stringify(data.ingredients)}
        })); true;`
      );
    } catch (e) {
      Alert.alert("Scan failed", e.message || String(e));
    } finally {
      notifyScanStatus(false);
    }
  }

const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
const voiceRun = useRef(0);
const recording = useRef(false);

function sendVoiceEvent(detail) {
  webRef.current?.injectJavaScript(`
    window.dispatchEvent(new CustomEvent("nosh-native-voice", {
      detail: ${JSON.stringify(detail)}
    }));
    true;
  `);
}

async function stopNativeListening() {
  voiceRun.current += 1;

  if (recording.current) {
    recording.current = false;
    await audioRecorder.stop();
  }

  sendVoiceEvent({ status: "ready" });
}

async function startNativeListening(token) {
  const run = ++voiceRun.current;

  try {
    const permission = await AudioModule.requestRecordingPermissionsAsync();

    if (!permission.granted) {
      throw new Error("Allow microphone access in your phone settings.");
    }

    await setAudioModeAsync({
      allowsRecording: true,
      playsInSilentMode: true,
    });

    await audioRecorder.prepareToRecordAsync();
    if (run !== voiceRun.current) return;

    audioRecorder.record();
    recording.current = true;
    sendVoiceEvent({ status: "listening" });

    await new Promise(resolve => setTimeout(resolve, 5000));
    if (run !== voiceRun.current) return;

    recording.current = false;
    await audioRecorder.stop();

    await setAudioModeAsync({
      allowsRecording: false,
      playsInSilentMode: true,
    });

    sendVoiceEvent({ status: "transcribing" });

    if (!audioRecorder.uri) {
      throw new Error("No audio was recorded.");
    }

    const form = new FormData();
    form.append("audio", new File(audioRecorder.uri));

    const response = await expoFetch(`${API}/voice/transcribe`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Could not transcribe your recording.");
    }

    if (run === voiceRun.current) {
      sendVoiceEvent({
        status: "ready",
        transcript: data.transcript || "",
      });
    }
  } catch (error) {
    if (run === voiceRun.current) {
      sendVoiceEvent({
        status: "ready",
        error: error.message || String(error),
      });
    }
  }
}

  async function openVideoCamera(token) {
    let permission = cameraPermission;

    if (!permission?.granted) {
      permission = await requestCameraPermission();
    }

    if (!permission?.granted) {
      Alert.alert("Camera permission is needed to record a video.");
      return;
    }

    setVideoToken(token);
    setCameraReady(false);
    setVideoMode(true);
  }

  async function uploadRecordedVideo(uri, token) {
    try {
      notifyScanStatus(true);
      const form = new FormData();
      form.append("video", new File(uri));

      const response = await expoFetch(`${API}/scan-video`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });

      if (!response.ok) {
        throw new Error(`Server said ${response.status}`);
      }

      const data = await response.json();

      webRef.current?.injectJavaScript(
        `window.dispatchEvent(new CustomEvent("nosh-scan", {
          detail: ${JSON.stringify(data.ingredients)}
        })); true;`
      );
    } catch (e) {
      Alert.alert("Video scan failed", e.message || String(e));
    } finally {
      notifyScanStatus(false);
    }
  }
  async function startOrStopVideoRecording() {
    if (!cameraRef.current || !cameraReady) {
      Alert.alert("Camera not ready", "Wait for the camera preview, then try again.");
      return;
    }

    if (isRecording) {
      cameraRef.current.stopRecording();
      return;
    }

    setIsRecording(true);

    try {
      const recordedVideo = await cameraRef.current.recordAsync({
        maxDuration: 30,
      });

      setIsRecording(false);
      setVideoMode(false);

      if (recordedVideo?.uri) {
        await uploadRecordedVideo(recordedVideo.uri, videoToken);
      }
    } catch (e) {
      setIsRecording(false);
      setVideoMode(false);
      Alert.alert("Recording failed", e.message || String(e));
    }
  }

  async function handleWebMessage(event) {
    let msg;

    try {
      msg = JSON.parse(event.nativeEvent.data);
    } catch {
      return;
    }

    if (msg.type === "scan") {
      Alert.alert("Scan fridge", "Choose a scan type", [
        { text: "Cancel", style: "cancel" },
        {
          text: "Record a video",
          onPress: () => openVideoCamera(msg.token),
        },
        {
          text: "Take a photo",
          onPress: () => scanWithCamera(msg.token),
        },
      ]);
    }
    if (msg.type === "native-listen") {
      void startNativeListening(msg.token || "");
      return;
    }

    if (msg.type === "native-listen-stop") {
      void stopNativeListening();
      return;
    }

    if (msg.type === "native-speak") {
      Speech.stop();
      Speech.speak(msg.text, {
        voice: "en-US-SMTf00",
        language: "en-US",
        rate: 0.95,
        pitch: 1,
      });
      return;
    }

    if (msg.type === "native-speak-stop") {
      Speech.stop();
      return;
    }
      }

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container} edges={["top", "bottom"]}>
        <View style={{ flex: 1 }}>
          <WebView
            ref={webRef}
            source={{ uri: APP_URL }}
            style={styles.web}
            originWhitelist={["*"]}
            javaScriptEnabled
            domStorageEnabled
            onMessage={handleWebMessage}
            setSupportMultipleWindows={true}
            onOpenWindow={({ nativeEvent }) => {
              const url = nativeEvent.targetUrl;
              if (url) Linking.openURL(url);
            }}
          />

          {videoMode && (
            <View style={StyleSheet.absoluteFill}>
              <CameraView
                ref={cameraRef}
                style={{ flex: 1 }}
                facing="back"
                mode="video"
                mute
                onCameraReady={() => setCameraReady(true)}
                onMountError={(event) => {
                  Alert.alert("Camera error", event.message);
                }}
              />

              <View style={styles.controls}>
                <Button
                  title={isRecording ? "Stop and scan" : "Start recording"}
                  onPress={startOrStopVideoRecording}
                />
                {!isRecording && (
                  <Button
                    title="Cancel"
                    onPress={() => setVideoMode(false)}
                  />
                )}
              </View>
            </View>
          )}
        </View>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#121010",
  },
  web: {
    flex: 1,
    backgroundColor: "#121010",
  },
  controls: {
    position: "absolute",
    bottom: 20,
    alignSelf: "center",
    gap: 10,
  },
});