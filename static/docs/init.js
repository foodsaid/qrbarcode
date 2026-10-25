// Kept out of index.html so the docs page needs no inline script.
window.addEventListener("load", function () {
  window.ui = SwaggerUIBundle({
    url: "/apispec.json",
    // Never let ?url= / ?configUrl= load someone else's spec into this page
    queryConfigEnabled: false,
    dom_id: "#swagger-ui",
    deepLinking: true,
    presets: [SwaggerUIBundle.presets.apis],
    layout: "BaseLayout",
    // Ready to call straight away: no "Try it out" click, no Schemas section
    tryItOutEnabled: true,
    displayRequestDuration: true,
    defaultModelsExpandDepth: -1,
    onComplete: function () {
      // Open /generate unless the URL already points at another operation
      if (!window.location.hash) {
        window.ui.layoutActions.show(["operations", "generate", "generateCode"], true);
      }
    },
  });
});
