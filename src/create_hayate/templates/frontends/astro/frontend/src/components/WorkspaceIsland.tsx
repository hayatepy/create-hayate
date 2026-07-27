import { useEffect, useState } from "preact/hooks";

import { createTodo, listTodos, type Todo } from "../api/client";

export default function WorkspaceIsland() {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState("Waiting to enter the browser…");
  const [ready, setReady] = useState(false);

  async function refresh() {
    const next = await listTodos();
    setTodos(next);
    setStatus(next.length ? "Private notes loaded from Hayate." : "Your private workspace is clear.");
  }

  useEffect(() => {
    let active = true;
    listTodos()
      .then((next) => {
        if (!active) return;
        setTodos(next);
        setStatus(
          next.length ? "Private notes loaded from Hayate." : "Your private workspace is clear.",
        );
      })
      .catch(() => active && setStatus("Hayate is unavailable. The static page still works."))
      .finally(() => active && setReady(true));
    return () => {
      active = false;
    };
  }, []);

  async function add(event: SubmitEvent) {
    event.preventDefault();
    const nextTitle = title.trim();
    if (!nextTitle) return;
    setStatus("Sending directly to Hayate…");
    try {
      await createTodo(nextTitle);
      setTitle("");
      await refresh();
    } catch {
      setStatus("Could not save that private note.");
    }
  }

  return (
    <section class="workspace-island" data-runtime-boundary="browser-only" aria-labelledby="workspace-title">
      <div class="island-heading">
        <div>
          <p class="section-label">Runtime island</p>
          <h2 id="workspace-title">Your private margin</h2>
        </div>
        <span class={ready ? "runtime-light ready" : "runtime-light"} aria-hidden="true" />
      </div>
      <p class="runtime-status" aria-live="polite">{status}</p>
      <form onSubmit={add}>
        <label for="private-note">A note for this identity</label>
        <div>
          <input
            id="private-note"
            value={title}
            onInput={(event) => setTitle(event.currentTarget.value)}
            maxLength={200}
            placeholder="Keep the next move close"
            required
          />
          <button type="submit">Save privately</button>
        </div>
      </form>
      {todos.length > 0 && (
        <ol class="private-notes" data-private-record-count={todos.length}>
          {todos.map((todo) => <li key={todo.id}>{todo.title}</li>)}
        </ol>
      )}
      <small>Fetched after hydration · same-origin credentials · never embedded at build</small>
    </section>
  );
}
