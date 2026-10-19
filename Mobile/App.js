import { useRef } from "react";
import { Alert, StatusBar, StyleSheet, View } from "react-native";
import { WebView } from "react-native-webview";
import * as ImagePicker from "expo-image-picker";
import { File } from "expo-file-system";

const APP_URL = "http://192.168.1.6:5173";
const API = "http://192.168.1.6:8000";

export default function App() {
  const webRef = useRef(null);

  async function scanWithCamera(token) {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("Camera permission is needed to scan your fridge");
      return;
    }

    const result = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (result.canceled) return;
    const photo = result.assets[0];

    try {
      const form = new FormData();
      form.append("image", new File(photo.uri));
      const response = await fetch(`${API}/scan`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form });
      if (!response.ok) throw new Error(`Server said ${response.status}`);
      const data = await response.json();
      webRef.current.injectJavaScript(
        `window.dispatchEvent(new CustomEvent("nosh-scan", { detail: ${JSON.stringify(
          data.ingredients
        )} })); true;`
      );
    } catch (e) {
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
          const msg = JSON.parse(e.nativeEvent.data);
          if (msg.type === "scan") scanWithCamera(msg.token);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#121010", paddingTop: StatusBar.currentHeight },
  web: { flex: 1, backgroundColor: "#121010" },
});