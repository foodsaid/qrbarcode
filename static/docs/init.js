// Kept out of index.html so the docs page needs no inline script.
window.addEventListener("load", function () {
  window.ui = SwaggerUIBundle({
    url: "/apispec.json",
    dom_id: "#swagger-ui",
    deepLinking: true,
    presets: [SwaggerUIBundle.presets.apis],
    layout: "BaseLayout",
  });
});
