import { useRef, useState } from "react";
import { Alert, Button, StyleSheet, Text, View,} from "react-native";
import { SafeAreaProvider, SafeAreaView, } from "react-native-safe-area-context";
import { WebView } from "react-native-webview";
import * as ImagePicker from "expo-image-picker";
import * as Speech from "expo-speech";
import { File } from "expo-file-system";
import { fetch as expoFetch } from "expo/fetch";
import { CameraView, useCameraPermissions } from "expo-camera";
import { AudioModule, RecordingPresets, setAudioModeAsync, useAudioRecorder, } from "expo-audio";

// Network endpoints for web app and backend API
const HOST = "192.168.79.150";
const APP_URL = `http://${HOST}:5173`;
const API = `http://${HOST}:8000`;

export default function App() {
  const webRef = useRef(null);
  const cameraRef = useRef(null);
  const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);

  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const [videoMode, setVideoMode] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [videoToken, setVideoToken] = useState("");
  const [cameraReady, setCameraReady] = useState(false);

  const [voiceRecipe, setVoiceRecipe] = useState(null);
  const [voiceToken, setVoiceToken] = useState("");
  const [voiceStep, setVoiceStep] = useState(0);
  const [voiceRecording, setVoiceRecording] = useState(false);
  const [voiceBusy, setVoiceBusy] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("");
  const voiceActiveRef = useRef(false);

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

  function speak(text) {
  return new Promise((resolve) => {
    Speech.stop();
    Speech.speak(text, {
      rate: 0.95,
      onDone: resolve,
      onStopped: resolve,
      onError: resolve,
    });
  });
}

async function speakStep(index, recipe) {
  const step = recipe?.steps?.[index];
  if (step) await speak(`Step ${index + 1}. ${step}`);
}

function stopVoiceCooking() {
  voiceActiveRef.current = false;
  Speech.stop();
  setVoiceStatus("Stopped listening.");
}

async function beginVoiceCooking(recipe, token) {
  if (!recipe?.steps?.length) {
    setVoiceStatus("The Cook page doesn't have recipe steps yet.");
    return;
  }

  try {
    const permission = await AudioModule.requestRecordingPermissionsAsync();
    if (!permission.granted) {
      setVoiceStatus("Allow microphone access to use voice cooking.");
      return;
    }

    const sessionResponse = await fetch(`${API}/voice/session`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        recipe_text: recipe.recipeText,
        ingredients: recipe.ingredients || [],
      }),
    });

    const sessionData = await sessionResponse.json();
    if (!sessionResponse.ok) {
      throw new Error(sessionData.detail || "Could not start the voice session.");
    }

    voiceActiveRef.current = true;
    setVoiceRecipe(recipe);
    setVoiceToken(token);
    setVoiceStep(0);
    setVoiceStatus("Starting voice cooking...");

    await setAudioModeAsync({
      allowsRecording: false,
      playsInSilentMode: true,
    });

    await speak(
      `Today we're making ${recipe.title}. I'll read the first step. Say next when you're ready. You can also ask a question, say repeat, or say stop.`
    );
    await speakStep(0, recipe);

    await listenForVoiceCommand(token);
  } catch (e) {
    voiceActiveRef.current = false;
    setVoiceStatus(`Voice cooking couldn't start: ${e.message || String(e)}`);
  }
}

async function listenForVoiceCommand(token) {
  if (!voiceActiveRef.current) return;

  try {
    setVoiceStatus("Listening… say next, repeat, back, or ask a question.");

    await setAudioModeAsync({
      allowsRecording: true,
      playsInSilentMode: true,
    });

    await audioRecorder.prepareToRecordAsync();
    await audioRecorder.record();

    // Record a short clip, then transcribe it.
    await new Promise((resolve) => setTimeout(resolve, 5000));

    if (!voiceActiveRef.current) {
      await audioRecorder.stop();
      return;
    }

    await audioRecorder.stop();
    await setAudioModeAsync({
      allowsRecording: false,
      playsInSilentMode: true,
    });

    const uri = audioRecorder.uri;
    if (!uri) {
      return listenForVoiceCommand(token);
    }

    const form = new FormData();
    form.append("audio", new File(uri));

    const transcriptResponse = await expoFetch(`${API}/voice/transcribe`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });

    const transcriptData = await transcriptResponse.json();
    if (!transcriptResponse.ok) {
      throw new Error(transcriptData.detail || "Could not transcribe that clip.");
    }

    const transcript = (transcriptData.transcript || "").trim();
    if (!transcript) {
      return listenForVoiceCommand(token);
    }

    if (/\b(stop|exit|quit)\b/i.test(transcript)) {
      stopVoiceCooking();
      await speak("Okay, I'll stop listening.");
      return;
    }

    setVoiceStatus(`Heard: ${transcript}`);
    const answerResponse = await fetch(`${API}/voice/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ question: transcript }),
    });

    const answerData = await answerResponse.json();
    if (!answerResponse.ok) {
      throw new Error(answerData.detail || "NOSH couldn't answer that.");
    }

    const answer = answerData.answer || "I don't have an answer for that.";
    const stepMatch = answer.match(/^Step (\d+)\b/i);
    if (stepMatch) setVoiceStep(Number(stepMatch[1]) - 1);

    setVoiceStatus(answer);
    await speak(answer);

    if (voiceActiveRef.current) {
      await listenForVoiceCommand(token);
    }
  } catch (e) {
    voiceActiveRef.current = false;
    setVoiceStatus(`Voice chat stopped: ${e.message || String(e)}`);
  }
}

  function handleWebMessage(event) {
    let msg;

    try {
      msg = JSON.parse(event.nativeEvent.data);
    } catch {
      return;
    }

    if (msg.type === "voice-cook") {
      beginVoiceCooking(msg.recipe, msg.token || "");
      return;
    }

    if (msg.type === "voice-stop") {
      stopVoiceCooking();
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
  }

  function closeVoiceCooking() {
    Speech.stop();
    setVoiceRecipe(null);
    setVoiceRecording(false);

    webRef.current?.injectJavaScript(
      `window.dispatchEvent(new Event("nosh-voice-done")); true;`
    );
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
          />

          {voiceRecipe && !videoMode && (
            <View style={styles.voicePanel}>
              <Text style={styles.voiceTitle}>{voiceRecipe.title}</Text>
              <Text style={styles.voiceText}>{voiceStatus}</Text>
              <Button title="Stop listening" onPress={stopVoiceCooking} />
            </View>
          )}

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
  voicePanel: {
    position: "absolute",
    left: 16,
    right: 16,
    bottom: 20,
    padding: 16,
    gap: 10,
    borderRadius: 16,
    backgroundColor: "#242020",
  },
  voiceTitle: {
    color: "white",
    fontSize: 18,
    fontWeight: "bold",
  },
  voiceText: {
    color: "white",
    marginBottom: 4,
  },
});