(() => {
  document.addEventListener("todo:created", () => {
    const input = document.querySelector("#new-todo");
    if (input instanceof HTMLInputElement) {
      input.value = "";
      input.focus();
    }
    document.querySelector("#todo-form-errors")?.replaceChildren();
  });

  document.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) {
      return;
    }
    const button = event.target.closest("#stream-demo");
    const output = document.querySelector("#stream-output");
    if (!(button instanceof HTMLButtonElement) || !(output instanceof HTMLOutputElement)) {
      return;
    }

    button.disabled = true;
    output.textContent = "";
    output.classList.add("is-streaming");
    const stream = new EventSource("/app/stream");
    let completed = false;

    stream.addEventListener("token", (message) => {
      const data = JSON.parse(message.data);
      if (typeof data.token === "string") {
        output.textContent += data.token;
      }
    });

    stream.addEventListener("done", () => {
      completed = true;
      stream.close();
      button.disabled = false;
      output.classList.remove("is-streaming");
    });

    stream.addEventListener("error", () => {
      stream.close();
      button.disabled = false;
      output.classList.remove("is-streaming");
      if (!completed) {
        output.textContent = "The stream stopped. Try again.";
      }
    });
  });
})();
