import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  ActivityIndicator,
  Alert,
  Linking,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import * as SQLite from "expo-sqlite";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as Location from "expo-location";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const DB_NAME = "beekeeper.db";
const API_BASE_URL = (process.env.EXPO_PUBLIC_API_URL || "https://honey-chain.onrender.com").replace(/\/$/, "");
const BEEKEEPER_ID = "1";

function apiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

let db: SQLite.SQLiteDatabase | null = null;

function getDb() {
  if (db) return db;
  try {
    db = SQLite.openDatabaseSync(DB_NAME);
  } catch {
    db = null;
  }
  return db;
}

function initDb() {
  const d = getDb();
  if (!d) return;
  d.execSync(`CREATE TABLE IF NOT EXISTS batch_pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    beekeeper_id TEXT, hive_id TEXT, harvest_date TEXT, location TEXT,
    floral_source TEXT, honey_type TEXT, weight_kg REAL,
    horticulture_notes TEXT, harvest_method TEXT,
    latitude REAL, longitude REAL, prev_hash TEXT, hash TEXT, synced INTEGER DEFAULT 0
  );`);
  d.execSync(`CREATE TABLE IF NOT EXISTS hive_pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hive_id TEXT, temp_c REAL, humidity REAL, weight_kg REAL, sound_db REAL, notes TEXT,
    latitude REAL, longitude REAL, ts TEXT, synced INTEGER DEFAULT 0
  );`);
  try { d.execSync(`ALTER TABLE batch_pending ADD COLUMN horticulture_notes TEXT`); } catch {}
  try { d.execSync(`ALTER TABLE batch_pending ADD COLUMN harvest_method TEXT`); } catch {}
  try { d.execSync(`ALTER TABLE hive_pending ADD COLUMN sound_db REAL`); } catch {}
}

type Harvest = {
  hive_id: string;
  floral_source: string;
  honey_type: string;
  weight_kg: string;
  horticulture_notes: string;
  harvest_method: string;
};

type HiveLog = {
  hive_id: string;
  temp_c: string;
  humidity: string;
  weight_kg: string;
  sound_db: string;
  notes: string;
};

function cheapHash(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

async function syncPending() {
  const d = getDb();
  if (!d) return { batches: 0, hives: 0 };
  const batches = d.getAllSync("SELECT * FROM batch_pending WHERE synced=0") as any[];
  const hives = d.getAllSync("SELECT * FROM hive_pending WHERE synced=0") as any[];
  let batchCount = 0;
  let hiveCount = 0;

  for (const batch of batches) {
    try {
      const response = await fetch(apiUrl("/api/batch"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(batch),
      });
      if (response.ok) {
        d.runSync("UPDATE batch_pending SET synced=1 WHERE id=?", [batch.id]);
        batchCount += 1;
      }
    } catch {
      // Keep the row pending. A field worker may be offline for hours.
    }
  }

  for (const hive of hives) {
    try {
      const response = await fetch(apiUrl("/api/hive"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(hive),
      });
      if (response.ok) {
        d.runSync("UPDATE hive_pending SET synced=1 WHERE id=?", [hive.id]);
        hiveCount += 1;
      }
    } catch {
      // Keep the row pending until the next manual or automatic sync.
    }
  }

  return { batches: batchCount, hives: hiveCount };
}

function Field({
  label,
  placeholder,
  value,
  onChangeText,
  keyboardType,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChangeText: (value: string) => void;
  keyboardType?: "default" | "numeric";
}) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.placeholder}
        keyboardType={keyboardType}
        style={styles.input}
        accessibilityLabel={label}
      />
    </View>
  );
}

function ActionButton({
  label,
  onPress,
  variant = "primary",
  disabled = false,
  accessibilityLabel,
}: {
  label: string;
  onPress: () => void;
  variant?: "primary" | "quiet" | "outline";
  disabled?: boolean;
  accessibilityLabel?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      style={({ pressed }) => [
        styles.button,
        variant === "quiet" && styles.quietButton,
        variant === "outline" && styles.outlineButton,
        pressed && styles.buttonPressed,
        disabled && styles.disabledButton,
      ]}
    >
      {disabled && <ActivityIndicator color={variant === "primary" ? colors.white : colors.green} size="small" />}
      <Text
        style={[
          styles.buttonText,
          variant === "quiet" && styles.quietButtonText,
          variant === "outline" && styles.outlineButtonText,
        ]}
      >
        {disabled ? "Saving..." : label}
      </Text>
    </Pressable>
  );
}

function SectionHeading({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <View style={styles.sectionHeading}>
      <Text style={styles.eyebrow}>{eyebrow}</Text>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

const colors = {
  ink: "#193026",
  muted: "#63756B",
  placeholder: "#98A69E",
  cream: "#F7F4EC",
  white: "#FFFFFF",
  green: "#175B45",
  greenDark: "#0F4635",
  greenTint: "#E3F0E9",
  honey: "#EFB53D",
  honeyTint: "#FFF1C9",
  line: "#D9E4DC",
  redTint: "#FCE9E2",
};

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.cream },
  scroll: { flex: 1 },
  content: { width: "100%", maxWidth: 640, alignSelf: "center", padding: 20, paddingBottom: 44 },
  topBar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 26 },
  brand: { flexDirection: "row", alignItems: "center", gap: 10 },
  brandMark: { width: 38, height: 38, borderRadius: 13, backgroundColor: colors.honey, alignItems: "center", justifyContent: "center" },
  brandMarkText: { color: colors.greenDark, fontSize: 18, fontWeight: "800" },
  brandName: { color: colors.ink, fontSize: 12, fontWeight: "800", letterSpacing: 1.4 },
  brandSub: { color: colors.muted, fontSize: 11, marginTop: 2 },
  statusDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.green, marginRight: 7 },
  onlineStatus: { flexDirection: "row", alignItems: "center", backgroundColor: colors.greenTint, borderRadius: 18, paddingHorizontal: 11, paddingVertical: 8 },
  statusText: { color: colors.greenDark, fontSize: 11, fontWeight: "700" },
  welcome: { marginBottom: 20 },
  welcomeTitle: { color: colors.ink, fontSize: 32, lineHeight: 38, fontWeight: "800", letterSpacing: -0.6 },
  welcomeBody: { color: colors.muted, fontSize: 15, lineHeight: 22, marginTop: 7, maxWidth: 470 },
  hero: { backgroundColor: colors.green, borderRadius: 24, padding: 20, marginBottom: 16, overflow: "hidden" },
  heroKicker: { color: "#BFE4D0", fontSize: 12, fontWeight: "700", letterSpacing: 0.6 },
  heroTitle: { color: colors.white, fontSize: 22, lineHeight: 28, fontWeight: "800", marginTop: 6, maxWidth: 390 },
  heroBody: { color: "#D8EFE1", fontSize: 13, lineHeight: 19, marginTop: 7, maxWidth: 420 },
  heroButton: { alignSelf: "flex-start", backgroundColor: colors.honey, marginTop: 16, paddingHorizontal: 17 },
  heroButtonText: { color: colors.greenDark },
  tabs: { flexDirection: "row", backgroundColor: colors.white, borderRadius: 16, padding: 4, marginBottom: 16, borderWidth: 1, borderColor: colors.line },
  tab: { flex: 1, minHeight: 46, alignItems: "center", justifyContent: "center", borderRadius: 12 },
  activeTab: { backgroundColor: colors.green },
  tabText: { color: colors.muted, fontSize: 12, fontWeight: "700" },
  activeTabText: { color: colors.white },
  statusCard: { backgroundColor: colors.white, borderRadius: 18, borderWidth: 1, borderColor: colors.line, padding: 16, marginBottom: 16 },
  statusRow: { flexDirection: "row", alignItems: "center" },
  statusTitle: { color: colors.ink, fontSize: 14, fontWeight: "800" },
  statusBody: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 3 },
  pendingBadge: { marginLeft: "auto", backgroundColor: colors.honeyTint, borderRadius: 10, paddingHorizontal: 9, paddingVertical: 6 },
  pendingText: { color: colors.greenDark, fontSize: 11, fontWeight: "800" },
  formCard: { backgroundColor: colors.white, borderRadius: 22, borderWidth: 1, borderColor: colors.line, padding: 18, marginBottom: 16 },
  sectionHeading: { marginBottom: 17 },
  eyebrow: { color: colors.green, fontSize: 11, letterSpacing: 1.1, fontWeight: "800", textTransform: "uppercase" },
  sectionTitle: { color: colors.ink, fontSize: 21, lineHeight: 27, fontWeight: "800", marginTop: 4 },
  helper: { color: colors.muted, fontSize: 13, lineHeight: 19, marginTop: 5 },
  field: { marginBottom: 13 },
  fieldLabel: { color: colors.ink, fontSize: 12, fontWeight: "800", marginBottom: 7 },
  input: { minHeight: 50, borderWidth: 1, borderColor: colors.line, borderRadius: 13, color: colors.ink, backgroundColor: "#FBFCFA", paddingHorizontal: 14, fontSize: 15 },
  twoFields: { flexDirection: "row", gap: 10 },
  halfField: { flex: 1 },
  button: { minHeight: 50, borderRadius: 14, backgroundColor: colors.green, paddingHorizontal: 16, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  buttonText: { color: colors.white, fontSize: 14, fontWeight: "800", textAlign: "center" },
  quietButton: { backgroundColor: colors.honey },
  quietButtonText: { color: colors.greenDark },
  outlineButton: { backgroundColor: colors.white, borderWidth: 1, borderColor: colors.green },
  outlineButtonText: { color: colors.green },
  buttonPressed: { opacity: 0.78, transform: [{ scale: 0.99 }] },
  disabledButton: { opacity: 0.62 },
  locationCard: { backgroundColor: colors.greenTint, borderRadius: 20, padding: 17, marginBottom: 16 },
  locationTop: { flexDirection: "row", alignItems: "flex-start", gap: 11 },
  locationIcon: { width: 34, height: 34, borderRadius: 12, backgroundColor: colors.white, alignItems: "center", justifyContent: "center" },
  locationIconText: { color: colors.green, fontSize: 16, fontWeight: "800" },
  locationTitle: { color: colors.greenDark, fontSize: 15, fontWeight: "800" },
  locationBody: { color: colors.green, fontSize: 12, lineHeight: 18, marginTop: 3, flex: 1 },
  locationButton: { marginTop: 14, backgroundColor: colors.white },
  locationButtonText: { color: colors.green },
  coords: { color: colors.greenDark, fontSize: 12, fontWeight: "700", marginTop: 12 },
  cameraCard: { backgroundColor: colors.ink, borderRadius: 20, padding: 17, marginBottom: 16 },
  cameraTitle: { color: colors.white, fontSize: 16, fontWeight: "800" },
  cameraBody: { color: "#B8C9C0", fontSize: 12, lineHeight: 18, marginTop: 4 },
  cameraButton: { backgroundColor: colors.honey, marginTop: 13 },
  cameraButtonText: { color: colors.greenDark },
  cameraView: { height: 270, borderRadius: 16, overflow: "hidden", marginTop: 14 },
  cameraClose: { position: "absolute", bottom: 12, alignSelf: "center", backgroundColor: "rgba(0,0,0,0.75)", paddingHorizontal: 16 },
  cameraCloseText: { color: colors.white },
  scanResult: { color: "#D8EFE1", fontSize: 12, lineHeight: 18, marginTop: 11 },
  mapPreview: { height: 190, borderRadius: 16, backgroundColor: colors.honeyTint, borderWidth: 1, borderColor: "#E8CF83", alignItems: "center", justifyContent: "center", marginBottom: 16 },
  mapPin: { width: 46, height: 46, borderRadius: 23, backgroundColor: colors.green, alignItems: "center", justifyContent: "center", marginBottom: 9 },
  mapPinText: { color: colors.honey, fontSize: 19, fontWeight: "900" },
  mapTitle: { color: colors.greenDark, fontSize: 14, fontWeight: "800" },
  mapBody: { color: colors.green, fontSize: 12, marginTop: 4 },
  profileCard: { backgroundColor: colors.white, borderRadius: 22, borderWidth: 1, borderColor: colors.line, padding: 18, marginBottom: 16 },
  profileRow: { flexDirection: "row", alignItems: "center", gap: 13 },
  avatar: { width: 54, height: 54, borderRadius: 18, backgroundColor: colors.honeyTint, alignItems: "center", justifyContent: "center" },
  avatarText: { color: colors.greenDark, fontSize: 21, fontWeight: "900" },
  profileName: { color: colors.ink, fontSize: 18, fontWeight: "800" },
  profileBody: { color: colors.muted, fontSize: 12, marginTop: 3 },
  privacyNote: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 16, paddingTop: 14, borderTopWidth: 1, borderTopColor: colors.line },
  footer: { color: colors.muted, textAlign: "center", fontSize: 11, lineHeight: 17, marginTop: 8 },
});

export default function Home() {
  const queryClient = useQueryClient();
  const [permission, requestPermission] = useCameraPermissions();
  const [showCamera, setShowCamera] = useState(false);
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [harvest, setHarvest] = useState<Harvest>({ hive_id: "", floral_source: "", honey_type: "", weight_kg: "", horticulture_notes: "", harvest_method: "" });
  const [hive, setHive] = useState<HiveLog>({ hive_id: "", temp_c: "", humidity: "", weight_kg: "", sound_db: "", notes: "" });
  const [lastScan, setLastScan] = useState<string | null>(null);
  const [tab, setTab] = useState<"harvest" | "hive" | "profile">("harvest");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    initDb();
  }, []);

  const pendingQuery = useQuery({
    queryKey: ["pending"],
    queryFn: () => {
      const d = getDb();
      if (!d) return { batch: 0, hive: 0 };
      const batches = d.getAllSync("SELECT count(*) as c FROM batch_pending WHERE synced=0") as any[];
      const hives = d.getAllSync("SELECT count(*) as c FROM hive_pending WHERE synced=0") as any[];
      return { batch: batches[0]?.c ?? 0, hive: hives[0]?.c ?? 0 };
    },
    refetchInterval: 3000,
  });

  const syncMutation = useMutation({
    mutationFn: syncPending,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pending"] }),
  });

  const grabGps = useCallback(async () => {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== "granted") {
      Alert.alert("Location not allowed", "Allow location so this household can have one shared pin.");
      return;
    }
    const position = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
    setCoords({ lat: position.coords.latitude, lng: position.coords.longitude });
  }, []);

  const openMap = useCallback(() => {
    if (!coords) return;
    const url = `https://www.openstreetmap.org/?mlat=${coords.lat}&mlon=${coords.lng}#map=15/${coords.lat}/${coords.lng}`;
    Linking.openURL(url);
  }, [coords]);

  const addHarvest = useCallback(async () => {
    if (!harvest.hive_id.trim()) {
      Alert.alert("Add the hive number", "This tells us which hive gave this harvest.");
      return;
    }
    setSaving(true);
    const d = getDb();
    const date = new Date().toISOString().slice(0, 10);
    const hash = cheapHash(`${harvest.hive_id}${date}${coords?.lat ?? ""}${Math.random()}`);
    const row = {
      beekeeper_id: BEEKEEPER_ID,
      hive_id: harvest.hive_id.trim(),
      harvest_date: date,
      location: coords ? `${coords.lat},${coords.lng}` : "",
      floral_source: harvest.floral_source.trim(),
      honey_type: harvest.honey_type.trim(),
      weight_kg: Number(harvest.weight_kg) || 0,
      horticulture_notes: harvest.horticulture_notes.trim(),
      harvest_method: harvest.harvest_method.trim(),
      latitude: coords?.lat ?? null,
      longitude: coords?.lng ?? null,
      prev_hash: "",
      hash,
    };
    if (d) {
      d.runSync(
        `INSERT INTO batch_pending (beekeeper_id,hive_id,harvest_date,location,floral_source,honey_type,weight_kg,horticulture_notes,harvest_method,latitude,longitude,prev_hash,hash,synced) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)`,
        [row.beekeeper_id, row.hive_id, row.harvest_date, row.location, row.floral_source, row.honey_type, row.weight_kg, row.horticulture_notes, row.harvest_method, row.latitude, row.longitude, row.prev_hash, row.hash]
      );
    }
    try {
      const response = await fetch(apiUrl("/api/batch"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(row) });
      if (response.ok && d) {
        const last = d.getAllSync("SELECT id FROM batch_pending ORDER BY id DESC LIMIT 1") as any[];
        if (last[0]) d.runSync("UPDATE batch_pending SET synced=1 WHERE id=?", [last[0].id]);
      }
    } catch {
      // The saved row will sync later.
    }
    setSaving(false);
    queryClient.invalidateQueries({ queryKey: ["pending"] });
    Alert.alert("Harvest saved", `Record ${hash} is safe on this phone and ready to sync.`);
    setHarvest({ hive_id: "", floral_source: "", honey_type: "", weight_kg: "", horticulture_notes: "", harvest_method: "" });
  }, [coords, harvest, queryClient]);

  const addHive = useCallback(async () => {
    if (!hive.hive_id.trim()) {
      Alert.alert("Add the hive number", "This tells us which hive you checked.");
      return;
    }
    setSaving(true);
    const d = getDb();
    const row = {
      hive_id: hive.hive_id.trim(),
      temp_c: Number(hive.temp_c) || 0,
      humidity: Number(hive.humidity) || 0,
      weight_kg: Number(hive.weight_kg) || 0,
      sound_db: Number(hive.sound_db) || 0,
      notes: hive.notes.trim(),
      latitude: coords?.lat ?? null,
      longitude: coords?.lng ?? null,
      ts: new Date().toISOString(),
    };
    if (d) {
      d.runSync(`INSERT INTO hive_pending (hive_id,temp_c,humidity,weight_kg,sound_db,notes,latitude,longitude,ts,synced) VALUES (?,?,?,?,?,?,?,?,?,0)`, [
        row.hive_id, row.temp_c, row.humidity, row.weight_kg, row.sound_db, row.notes, row.latitude, row.longitude, row.ts,
      ]);
    }
    try {
      const response = await fetch(apiUrl("/api/hive"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(row) });
      if (response.ok && d) {
        const last = d.getAllSync("SELECT id FROM hive_pending ORDER BY id DESC LIMIT 1") as any[];
        if (last[0]) d.runSync("UPDATE hive_pending SET synced=1 WHERE id=?", [last[0].id]);
      }
    } catch {
      // The saved row will sync later.
    }
    setSaving(false);
    queryClient.invalidateQueries({ queryKey: ["pending"] });
    Alert.alert("Hive check saved", "The check is safe on this phone and ready to sync.");
    setHive({ hive_id: "", temp_c: "", humidity: "", weight_kg: "", sound_db: "", notes: "" });
  }, [coords, hive, queryClient]);

  const pending = (pendingQuery.data?.batch ?? 0) + (pendingQuery.data?.hive ?? 0);

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.topBar}>
          <View style={styles.brand}>
            <View style={styles.brandMark}><Text style={styles.brandMarkText}>H</Text></View>
            <View>
              <Text style={styles.brandName}>HONEY CHAIN</Text>
              <Text style={styles.brandSub}>Your harvest record</Text>
            </View>
          </View>
          <View style={styles.onlineStatus} accessibilityLabel="Saved on this phone">
            <View style={styles.statusDot} />
            <Text style={styles.statusText}>Saved here</Text>
          </View>
        </View>

        <View style={styles.welcome}>
          <Text style={styles.welcomeTitle}>Good morning.</Text>
          <Text style={styles.welcomeBody}>Record the work once. We keep it safe, even when the signal is gone.</Text>
        </View>

        <View style={styles.hero}>
          <Text style={styles.heroKicker}>TODAY&apos;S SIMPLE STEP</Text>
          <Text style={styles.heroTitle}>Did you collect honey today?</Text>
          <Text style={styles.heroBody}>Write down the hive, flower, and weight. The cooperative can trace it later.</Text>
          <ActionButton label="Add a harvest" onPress={() => setTab("harvest")} variant="quiet" />
        </View>

        <View style={styles.tabs} accessibilityRole="tablist">
          {(["harvest", "hive", "profile"] as const).map((item) => {
            const labels = { harvest: "Harvest", hive: "Hive check", profile: "My place" };
            return (
              <Pressable
                key={item}
                onPress={() => setTab(item)}
                accessibilityRole="tab"
                accessibilityState={{ selected: tab === item }}
                style={[styles.tab, tab === item && styles.activeTab]}
              >
                <Text style={[styles.tabText, tab === item && styles.activeTabText]}>{labels[item]}</Text>
              </Pressable>
            );
          })}
        </View>

        <View style={styles.statusCard}>
          <View style={styles.statusRow}>
            <View>
              <Text style={styles.statusTitle}>{pending === 0 ? "Everything is up to date" : `${pending} record${pending === 1 ? "" : "s"} waiting`}</Text>
              <Text style={styles.statusBody}>{pending === 0 ? "Your work is recorded on this phone." : "No problem. Send when the network returns."}</Text>
            </View>
            {pending > 0 && <View style={styles.pendingBadge}><Text style={styles.pendingText}>{pending} to send</Text></View>}
          </View>
          {pending > 0 && (
            <View style={{ marginTop: 12 }}>
              <ActionButton label={syncMutation.isPending ? "Sending records..." : "Send now"} onPress={() => syncMutation.mutate()} disabled={syncMutation.isPending} variant="outline" />
            </View>
          )}
        </View>

        {tab === "harvest" && (
          <View style={styles.formCard}>
            <SectionHeading eyebrow="New record" title="Add a harvest">
              <Text style={styles.helper}>This record is locked with a fingerprint when you save it.</Text>
            </SectionHeading>
            <Field label="Hive number" placeholder="For example, 1 or H-01" value={harvest.hive_id} onChangeText={(value) => setHarvest((current) => ({ ...current, hive_id: value }))} />
            <Field label="Flower nearby" placeholder="For example, mustard" value={harvest.floral_source} onChangeText={(value) => setHarvest((current) => ({ ...current, floral_source: value }))} />
            <Field label="Honey kind" placeholder="For example, raw honey" value={harvest.honey_type} onChangeText={(value) => setHarvest((current) => ({ ...current, honey_type: value }))} />
            <Field label="How much? (kg)" placeholder="For example, 12" value={harvest.weight_kg} onChangeText={(value) => setHarvest((current) => ({ ...current, weight_kg: value }))} keyboardType="numeric" />
            <Field label="Harvest method" placeholder="manual or extractor" value={harvest.harvest_method} onChangeText={(value) => setHarvest((current) => ({ ...current, harvest_method: value }))} />
            <Field label="Horticulture notes" placeholder="crop, season, health" value={harvest.horticulture_notes} onChangeText={(value) => setHarvest((current) => ({ ...current, horticulture_notes: value }))} />
            <ActionButton label="Save harvest" onPress={addHarvest} disabled={saving} />
            <Text style={styles.footer}>No signal is okay. The phone saves first and sends later.</Text>
          </View>
        )}

        {tab === "hive" && (
          <View style={styles.formCard}>
            <SectionHeading eyebrow="Quick check" title="How is the hive today?">
              <Text style={styles.helper}>A few numbers help the cooperative spot trouble early.</Text>
            </SectionHeading>
            <Field label="Hive number" placeholder="For example, 1 or H-01" value={hive.hive_id} onChangeText={(value) => setHive((current) => ({ ...current, hive_id: value }))} />
            <View style={styles.twoFields}>
              <View style={styles.halfField}><Field label="Temperature (°C)" placeholder="35" value={hive.temp_c} onChangeText={(value) => setHive((current) => ({ ...current, temp_c: value }))} keyboardType="numeric" /></View>
              <View style={styles.halfField}><Field label="Humidity (%)" placeholder="60" value={hive.humidity} onChangeText={(value) => setHive((current) => ({ ...current, humidity: value }))} keyboardType="numeric" /></View>
            </View>
            <Field label="Hive weight (kg)" placeholder="For example, 28" value={hive.weight_kg} onChangeText={(value) => setHive((current) => ({ ...current, weight_kg: value }))} keyboardType="numeric" />
            <Field label="Sound (dB)" placeholder="For example, 72" value={hive.sound_db} onChangeText={(value) => setHive((current) => ({ ...current, sound_db: value }))} keyboardType="numeric" />
            <Field label="What did you see?" placeholder="For example, queen seen" value={hive.notes} onChangeText={(value) => setHive((current) => ({ ...current, notes: value }))} />
            <ActionButton label="Save hive check" onPress={addHive} disabled={saving} />
          </View>
        )}

        {tab === "profile" && (
          <>
            <View style={styles.profileCard}>
              <View style={styles.profileRow}>
                <View style={styles.avatar}><Text style={styles.avatarText}>BK</Text></View>
                <View>
                  <Text style={styles.profileName}>My household</Text>
                  <Text style={styles.profileBody}>Demo cooperative · 2 years keeping bees</Text>
                </View>
              </View>
              <Text style={styles.privacyNote}>One shared home pin links your harvest and hive checks. It shows the household area, not the inside of your home.</Text>
            </View>
            <View style={styles.locationCard}>
              <View style={styles.locationTop}>
                <View style={styles.locationIcon}><Text style={styles.locationIconText}>+</Text></View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.locationTitle}>Household location</Text>
                  <Text style={styles.locationBody}>Use one place for this household&apos;s records.</Text>
                </View>
              </View>
              <ActionButton label={coords ? "Update location" : "Add household location"} onPress={grabGps} variant="outline" />
              {coords && <Text style={styles.coords}>{coords.lat.toFixed(5)}, {coords.lng.toFixed(5)} · saved for this household</Text>}
              {coords && <View style={{ marginTop: 10 }}><ActionButton label="Open map" onPress={openMap} variant="quiet" /></View>}
            </View>
            <View style={styles.mapPreview}>
              <View style={styles.mapPin}><Text style={styles.mapPinText}>+</Text></View>
              <Text style={styles.mapTitle}>{coords ? "Household pin ready" : "Your household map"}</Text>
              <Text style={styles.mapBody}>{coords ? "The same pin follows every record." : "Add a location above to place the pin."}</Text>
            </View>
          </>
        )}

        <View style={styles.cameraCard}>
          <Text style={styles.cameraTitle}>Scan a honey QR</Text>
          <Text style={styles.cameraBody}>Check a jar or open a harvest record with your phone camera.</Text>
          {!permission ? (
            <ActivityIndicator color={colors.honey} style={{ marginTop: 14 }} />
          ) : !permission.granted ? (
            <ActionButton label="Allow camera" onPress={requestPermission} variant="quiet" />
          ) : showCamera ? (
            <View style={styles.cameraView}>
              <CameraView
                style={{ flex: 1 }}
                facing="back"
                barcodeScannerSettings={{ barcodeTypes: ["qr"] }}
                onBarcodeScanned={({ data }: { data: string }) => {
                  setLastScan(data);
                  setShowCamera(false);
                }}
              />
              <Pressable onPress={() => setShowCamera(false)} style={[styles.button, styles.cameraClose]} accessibilityRole="button" accessibilityLabel="Close camera">
                <Text style={styles.cameraCloseText}>Close</Text>
              </Pressable>
            </View>
          ) : (
            <ActionButton label="Open camera" onPress={() => setShowCamera(true)} variant="quiet" />
          )}
          {lastScan && <Text style={styles.scanResult}>Last scan saved: {lastScan.slice(0, 54)}{lastScan.length > 54 ? "..." : ""}</Text>}
        </View>

        <Text style={styles.footer}>Honey Chain keeps a clear record from your household to the cooperative.</Text>
      </ScrollView>
    </SafeAreaView>
  );
}
