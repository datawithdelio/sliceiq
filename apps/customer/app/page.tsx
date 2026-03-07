export default function Home() {
  return (
    <div className="min-h-screen bg-white text-zinc-900">
      <main className="mx-auto flex max-w-5xl flex-col gap-10 px-6 py-16">
        <header className="space-y-4">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-zinc-500">
            SliceIQ
          </p>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
            Smarter slices, happier customers.
          </h1>
          <p className="max-w-2xl text-lg text-zinc-600">
            Personalized menu recommendations, seamless ordering, and real-time
            insights for every pizza lover.
          </p>
        </header>

        <section className="grid gap-6 sm:grid-cols-3">
          <div className="rounded-2xl border border-zinc-200 p-6 shadow-sm">
            <h2 className="text-lg font-semibold">Personalized Picks</h2>
            <p className="mt-2 text-sm text-zinc-600">
              AI-powered suggestions tailored to each customer.
            </p>
          </div>
          <div className="rounded-2xl border border-zinc-200 p-6 shadow-sm">
            <h2 className="text-lg font-semibold">Fast Ordering</h2>
            <p className="mt-2 text-sm text-zinc-600">
              One-tap reorders and saved preferences for speed.
            </p>
          </div>
          <div className="rounded-2xl border border-zinc-200 p-6 shadow-sm">
            <h2 className="text-lg font-semibold">Loyalty Rewards</h2>
            <p className="mt-2 text-sm text-zinc-600">
              Earn points and unlock perks with every slice.
            </p>
          </div>
        </section>

        <div>
          <button className="rounded-full bg-zinc-900 px-6 py-3 text-sm font-semibold text-white">
            Get Started
          </button>
        </div>
      </main>
    </div>
  );
}
