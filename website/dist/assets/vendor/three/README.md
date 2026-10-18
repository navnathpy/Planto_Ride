Three.js 0.186.1 — locally bundled for Planto-Ride
================================================

Source: https://registry.npmjs.org/three/-/three-0.186.1.tgz
Project: https://threejs.org/
License: MIT; see LICENSE and the preserved notice in the bundled module.

The browser module contains only the renderer, geometry, lighting and material exports used by scene.mjs. It was bundled with the project's existing esbuild executable, with `--bundle --minify --format=esm --target=es2022 --legal-comments=eof`. It has no external runtime imports.

The car, planting and traffic geometry is created by Planto-Ride's scene.mjs. There are no externally licensed vehicle models or textures; the door and bonnet emblem uses the project's supplied logo.
