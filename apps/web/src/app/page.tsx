"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "https://honey-chain.onrender.com";

type Batch = { hash: string; flower_source: string; honey_type: string; hive_id: string; harvest_date: string; location: string; beekeeper_name?: string; };
type Beekeeper = { id: number; name: string; village: string; collective_name?: string; };

export default function Home() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [keepers, setKeepers] = useState<Beekeeper[]>([]);
  const [form, setForm] = useState({ beekeeper_id: "1", hive_id: "HIVE-01", harvest_date: new Date().toISOString().slice(0,10), location: "", honey_type: "raw", flower_source: "mustard", weight_kg: "", harvest_method: "extractor", horticulture_notes: "" });
  const [hive, setHive] = useState({ hive_id: "HIVE-01", beekeeper_id: "1", temperature: "", humidity: "", weight: "", sound_db: "" });

  useEffect(() => {
    fetch(`${API}/api/batches`).then(r=>r.json()).then(setBatches).catch(()=>{});
    fetch(`${API}/api/beekeepers`).then(r=>r.json()).then(setKeepers).catch(()=>{});
  }, []);

  const postBatch = async (e: React.FormEvent) => {
    e.preventDefault();
    const fd = new URLSearchParams(form as any);
    await fetch(`${API}/api/batch`, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: fd.toString() });
    location.reload();
  };
  const postHive = async (e: React.FormEvent) => {
    e.preventDefault();
    const fd = new URLSearchParams(hive as any);
    await fetch(`${API}/api/hive`, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: fd.toString() });
    location.reload();
  };

  return (
    <main className="max-w-5xl mx-auto p-6 font-sans">
      <header className="flex justify-between items-center border-b pb-4 mb-6">
        <div><h1 className="text-2xl font-bold">Honey Chain</h1><p className="text-sm text-zinc-500">KVIC prototype — hash chain + QR + hive check + map</p></div>
        <nav className="flex gap-4 text-sm"><a href="/" className="font-bold">Home</a><a href={`${API}/promotion`}>Promotion</a><a href={`${API}/beekeeper`}>Beekeepers</a><a href={`${API}/collectives`}>Collectives</a><a href={`${API}/pooled`}>Pooled</a></nav>
      </header>

      <section className="border rounded-xl p-4 mb-8">
        <h2 className="font-semibold mb-3">Add harvest batch</h2>
        <form onSubmit={postBatch} className="grid grid-cols-2 gap-3">
          <label>Beekeeper<select value={form.beekeeper_id} onChange={e=>setForm({...form, beekeeper_id:e.target.value})} className="w-full border rounded p-2">{keepers.map(k=><option key={k.id} value={k.id}>{k.name} — {k.village} {k.collective_name?`— ${k.collective_name}`:""}</option>)}{keepers.length===0 && <option value="1">1 — Ramesh</option>}</select></label>
          <label>Hive ID<input value={form.hive_id} onChange={e=>setForm({...form, hive_id:e.target.value})} className="w-full border rounded p-2" required /></label>
          <label>Harvest date<input type="date" value={form.harvest_date} onChange={e=>setForm({...form, harvest_date:e.target.value})} className="w-full border rounded p-2" required /></label>
          <label>Location<input value={form.location} onChange={e=>setForm({...form, location:e.target.value})} placeholder="village, district" className="w-full border rounded p-2" /></label>
          <label>Honey type<input value={form.honey_type} onChange={e=>setForm({...form, honey_type:e.target.value})} placeholder="raw" className="w-full border rounded p-2" /></label>
          <label>Flower source<input value={form.flower_source} onChange={e=>setForm({...form, flower_source:e.target.value})} placeholder="mustard" className="w-full border rounded p-2" /></label>
          <label>Weight kg<input value={form.weight_kg} onChange={e=>setForm({...form, weight_kg:e.target.value})} className="w-full border rounded p-2" /></label>
          <label>Harvest method<input value={form.harvest_method} onChange={e=>setForm({...form, harvest_method:e.target.value})} placeholder="extractor" className="w-full border rounded p-2" /></label>
          <label className="col-span-2">Horticulture notes<textarea value={form.horticulture_notes} onChange={e=>setForm({...form, horticulture_notes:e.target.value})} className="w-full border rounded p-2" /></label>
          <button type="submit" className="col-span-2 bg-amber-400 rounded p-3 font-semibold">Create batch and generate hash</button>
        </form>
      </section>

      <section className="mb-8">
        <h2 className="font-semibold mb-3">Recent batches</h2>
        {batches.length===0 ? <p>No batches yet.</p> : batches.slice(0,10).map(b=>(
          <div key={b.hash} className="border rounded p-3 mb-2"><div className="font-semibold">{b.honey_type || "Honey"} — {b.flower_source || "-" } <span className="bg-amber-100 text-xs px-2 py-1 rounded-full ml-2">{b.hash.slice(0,10)}...</span></div><div className="text-sm text-zinc-600">Hive {b.hive_id} | {b.harvest_date} | {b.location}</div><div className="text-sm mt-1"><a href={`${API}/verify/${b.hash}`} className="underline">Verify</a> • <a href={`${API}/beekeeper/${b.hash}`} className="underline">Know your beekeeper</a></div></div>
        ))}
      </section>

      <section className="border rounded-xl p-4">
        <h2 className="font-semibold mb-3">Hive telemetry — quick log</h2>
        <form onSubmit={postHive} className="grid grid-cols-2 gap-3">
          <label>Hive ID<input value={hive.hive_id} onChange={e=>setHive({...hive, hive_id:e.target.value})} className="w-full border rounded p-2" required /></label>
          <label>Beekeeper<select value={hive.beekeeper_id} onChange={e=>setHive({...hive, beekeeper_id:e.target.value})} className="w-full border rounded p-2">{keepers.map(k=><option key={k.id} value={k.id}>{k.name}</option>)}</select></label>
          <label>Temperature C<input value={hive.temperature} onChange={e=>setHive({...hive, temperature:e.target.value})} className="w-full border rounded p-2" /></label>
          <label>Humidity %<input value={hive.humidity} onChange={e=>setHive({...hive, humidity:e.target.value})} className="w-full border rounded p-2" /></label>
          <label>Weight kg<input value={hive.weight} onChange={e=>setHive({...hive, weight:e.target.value})} className="w-full border rounded p-2" /></label>
          <label>Sound dB<input value={hive.sound_db} onChange={e=>setHive({...hive, sound_db:e.target.value})} className="w-full border rounded p-2" /></label>
          <button type="submit" className="col-span-2 bg-amber-400 rounded p-3 font-semibold">Log reading</button>
        </form>
        <p className="text-xs text-zinc-500 mt-2">Flags: temp &gt;35, humidity &lt;40, sound &gt;85. Hash is fingerprint, prev_hash links.</p>
      </section>
    </main>
  );
}
