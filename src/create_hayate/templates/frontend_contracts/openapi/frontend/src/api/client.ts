import type { paths } from "./schema";
import { createHayateClient } from "./transport";

export type Todo =
  paths["/api/todos"]["get"]["responses"][200]["content"]["application/json"][number];

const runtimeOrigin =
  typeof window === "undefined" ? "https://build-time-data.invalid" : window.location.origin;

const client = createHayateClient({
  baseUrl: runtimeOrigin,
  credentials: "include",
});

function requestError(response: Response): Error {
  return new Error(`Hayate request failed ($${response.status} $${response.statusText})`);
}

export async function listTodos(): Promise<Todo[]> {
  const response = await client.listTodos();
  if (response.status !== 200) {
    throw requestError(response);
  }
  return response.json();
}

export async function createTodo(title: string): Promise<Todo> {
  const response = await client.createTodo({
    json: { title },
  });
  if (response.status !== 201) {
    throw requestError(response);
  }
  return response.json();
}

export async function updateTodo(id: string, title: string): Promise<Todo> {
  const response = await client.updateTodo({
    path: { id },
    json: { title },
  });
  if (response.status !== 200) {
    throw requestError(response);
  }
  return response.json();
}

export async function deleteTodo(id: string): Promise<void> {
  const response = await client.deleteTodo({
    path: { id },
  });
  if (response.status !== 204) {
    throw requestError(response);
  }
}
