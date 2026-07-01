import type { Me } from "./lib/api";

export default function Dashboard({ me }: { me: Me }) {
  return (
    <main className="grid gap-4 p-6 md:grid-cols-3">
      <section className="rounded-lg border bg-white p-4"><h3 className="text-sm text-gray-500">Balance</h3><p className="text-2xl font-semibold">$—</p></section>
      <section className="rounded-lg border bg-white p-4"><h3 className="text-sm text-gray-500">Positions</h3><p className="text-sm text-gray-400">None yet.</p></section>
      <section className="rounded-lg border bg-white p-4"><h3 className="text-sm text-gray-500">Hypotheses</h3>
        <p className="text-sm text-gray-400">{me.execution_enabled ? "Owner: approval queue (Week 7)." : "Read-only tier."}</p>
      </section>
    </main>
  );
}