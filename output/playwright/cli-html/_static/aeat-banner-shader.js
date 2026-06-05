(function () {
  "use strict";

  var motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  var schemeQuery = window.matchMedia("(prefers-color-scheme: dark)");

  var vertexSource = [
    "attribute vec2 a_position;",
    "void main() {",
    "  gl_Position = vec4(a_position, 0.0, 1.0);",
    "}",
  ].join("\n");

  var fragmentSource = [
    "precision mediump float;",
    "uniform vec2 u_resolution;",
    "uniform float u_time;",
    "uniform float u_dark;",
    "float softOrb(vec2 uv, vec2 center, float radius) {",
    "  float d = distance(uv, center);",
    "  return 1.0 - smoothstep(0.0, radius, d);",
    "}",
    "void main() {",
    "  vec2 uv = gl_FragCoord.xy / max(u_resolution, vec2(1.0));",
    "  float t = u_time * 0.11;",
    "  vec2 leftCenter = vec2(0.18 + sin(t) * 0.05, 0.25 + cos(t * 0.72) * 0.06);",
    "  vec2 rightCenter = vec2(0.84 + cos(t * 0.84) * 0.06, 0.72 + sin(t * 0.68) * 0.05);",
    "  vec2 lowCenter = vec2(0.46 + sin(t * 0.52) * 0.05, 0.04 + cos(t * 0.61) * 0.04);",
    "  float diagonal = smoothstep(-0.08, 1.08, uv.x * 0.64 + (1.0 - uv.y) * 0.36 + sin(t + uv.y * 2.4) * 0.025);",
    "  float glowA = softOrb(uv, leftCenter, 0.82);",
    "  float glowB = softOrb(uv, rightCenter, 0.76);",
    "  float glowC = softOrb(uv, lowCenter, 0.68);",
    "  vec3 brandBlue = vec3(0.0, 0.439, 0.953);",
    "  vec3 coolBlue = vec3(0.46, 0.70, 1.0);",
    "  vec3 lightBase = vec3(0.955, 0.974, 0.996);",
    "  vec3 lightGlow = vec3(1.0, 1.0, 1.0);",
    "  vec3 darkBase = vec3(0.024, 0.033, 0.048);",
    "  vec3 darkGlow = vec3(0.070, 0.185, 0.315);",
    "  vec3 lightInk = mix(lightBase, coolBlue, glowA * 0.30 + diagonal * 0.18);",
    "  lightInk = mix(lightInk, lightGlow, glowB * 0.28);",
    "  lightInk = mix(lightInk, brandBlue, glowC * 0.10);",
    "  vec3 darkInk = mix(darkBase, darkGlow, glowA * 0.60 + diagonal * 0.30);",
    "  darkInk = mix(darkInk, coolBlue, glowB * 0.20 + glowC * 0.14);",
    "  vec3 ink = mix(lightInk, darkInk, u_dark);",
    "  float alpha = mix(0.96, 0.94, u_dark);",
    "  gl_FragColor = vec4(ink, alpha);",
    "}",
  ].join("\n");

  function compile(gl, type, source) {
    var shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  }

  function createProgram(gl) {
    var vertex = compile(gl, gl.VERTEX_SHADER, vertexSource);
    var fragment = compile(gl, gl.FRAGMENT_SHADER, fragmentSource);
    if (!vertex || !fragment) {
      return null;
    }
    var program = gl.createProgram();
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    gl.deleteShader(vertex);
    gl.deleteShader(fragment);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      gl.deleteProgram(program);
      return null;
    }
    return program;
  }

  function isDarkTheme() {
    var theme = document.body.getAttribute("data-theme");
    if (theme === "dark") {
      return 1;
    }
    if (theme === "light") {
      return 0;
    }
    return schemeQuery.matches ? 1 : 0;
  }

  function addQueryListener(query, handler) {
    if (query.addEventListener) {
      query.addEventListener("change", handler);
      return;
    }
    query.addListener(handler);
  }

  function start(canvas) {
    if (motionQuery.matches || canvas.dataset.aeatShaderReady === "true") {
      return;
    }

    var gl = canvas.getContext("webgl", {
      alpha: true,
      antialias: false,
      depth: false,
      preserveDrawingBuffer: true,
      powerPreference: "low-power",
      stencil: false,
    });
    if (!gl) {
      canvas.dataset.aeatShaderReady = "false";
      canvas.dataset.aeatShaderError = "webgl-unavailable";
      return;
    }

    var program = createProgram(gl);
    if (!program) {
      canvas.dataset.aeatShaderReady = "false";
      canvas.dataset.aeatShaderError = "program-unavailable";
      return;
    }

    var buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    );

    var position = gl.getAttribLocation(program, "a_position");
    var resolution = gl.getUniformLocation(program, "u_resolution");
    var time = gl.getUniformLocation(program, "u_time");
    var dark = gl.getUniformLocation(program, "u_dark");
    var startTime = performance.now();
    var frame = 0;
    var fallback = 0;
    var frameCount = 0;
    var lastFrameAt = 0;

    canvas.dataset.aeatShaderReady = "true";
    canvas.dataset.aeatShaderFrame = "0";

    function resize() {
      var rect = canvas.getBoundingClientRect();
      var scale = Math.min(window.devicePixelRatio || 1, 1.6);
      var width = Math.max(1, Math.floor(rect.width * scale));
      var height = Math.max(1, Math.floor(rect.height * scale));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      gl.viewport(0, 0, width, height);
    }

    function paint(now) {
      if (motionQuery.matches || !document.documentElement.contains(canvas)) {
        if (fallback) {
          window.clearInterval(fallback);
          fallback = 0;
        }
        return false;
      }
      resize();
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.useProgram(program);
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.enableVertexAttribArray(position);
      gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
      gl.uniform2f(resolution, canvas.width, canvas.height);
      gl.uniform1f(time, (now - startTime) / 1000);
      gl.uniform1f(dark, isDarkTheme());
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      frameCount += 1;
      lastFrameAt = now;
      canvas.dataset.aeatShaderFrame = String(frameCount);
      return true;
    }

    function draw(now) {
      if (!paint(now)) {
        frame = 0;
        return;
      }
      frame = window.requestAnimationFrame(draw);
    }

    if ("ResizeObserver" in window) {
      new ResizeObserver(resize).observe(canvas);
    } else {
      window.addEventListener("resize", resize, { passive: true });
    }

    addQueryListener(motionQuery, function () {
      if (motionQuery.matches && frame) {
        window.cancelAnimationFrame(frame);
        frame = 0;
      } else if (!frame) {
        startTime = performance.now();
        frame = window.requestAnimationFrame(draw);
      }
    });
    addQueryListener(schemeQuery, function () {
      paint(performance.now());
    });

    paint(performance.now());
    frame = window.requestAnimationFrame(draw);
    fallback = window.setInterval(function () {
      var now = performance.now();
      if (now - lastFrameAt > 180) {
        paint(now);
      }
    }, 120);
  }

  function boot() {
    if (motionQuery.matches) {
      return;
    }
    document.querySelectorAll("[data-aeat-brand-shader]").forEach(start);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
