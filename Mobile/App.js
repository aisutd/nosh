import { useRef } from "react";
import { Alert, StatusBar, StyleSheet, View } from "react-native";
import { WebView } from "react-native-webview";
import * as ImagePicker from "expo-image-picker";
import { File } from "expo-file-system";

// Network endpoints for web app and backend API
const HOST = "192.168.1.6";               // <- only line to change on a new network
const APP_URL = `http://${HOST}:5173`;    // the React site (Vite)
const API = `http://${HOST}:8000`;        // the FastAPI backend

export default function App() {
  // Reference to control the WebView component
  const webRef = useRef(null);

  // Function to open the camera, take a fridge photo, and send it to the backend
  async function scanWithCamera(token) {
    // Request permission to use the device camera
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("Camera permission is needed to scan your fridge");
      return;
    }

    // Launch camera and wait for a photo capture
    const result = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (result.canceled) return;
    const photo = result.assets[0];

    try {
      // Package the captured photo into a form payload
      const form = new FormData();
      form.append("image", new File(photo.uri));
      // Send the image to the backend scan route with authentication
      const response = await fetch(`${API}/scan`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form });
      if (!response.ok) throw new Error(`Server said ${response.status}`);
      const data = await response.json();
      // Pass the detected ingredients back into the WebView via a custom JavaScript event
      webRef.current.injectJavaScript(
        `window.dispatchEvent(new CustomEvent("nosh-scan", { detail: ${JSON.stringify(
          data.ingredients
        )} })); true;`
      );
    } catch (e) {
      // Alert the user if the scanning or upload process fails
      Alert.alert("Scan failed", String(e.message));
    }
  }

  return (
    <View style={styles.container}>
      <WebView
        ref={webRef}
        source={{ uri: APP_URL }}
        style={styles.web}
        originWhitelist={["*"]}
        javaScriptEnabled
        domStorageEnabled
        onMessage={(e) => {
          // Listen for messages triggered from inside the web app
          const msg = JSON.parse(e.nativeEvent.data);
          if (msg.type === "scan") scanWithCamera(msg.token);
        }}
      />
    </View>
  );
}

// Layout styling for container and WebView elements
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#121010", paddingTop: StatusBar.currentHeight },
  web: { flex: 1, backgroundColor: "#121010" },
});