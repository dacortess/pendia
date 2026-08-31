# ADR-006: Estructura del frontend Next.js

## Contexto

Cloudflare Pages Free sirve sitios estáticos sin fricción; servir SSR
requiere el adaptador `@cloudflare/next-on-pages` con Edge Runtime, que
impone restricciones (no todo paquete Node funciona en Edge) y acopla el
frontend a runtime de Cloudflare. Como **toda** la lógica de negocio y auth
ya vive en FastAPI (ADR-001, ADR-005), el frontend no necesita SSR real:
solo necesita renderizar UI y consumir la API vía fetch desde el cliente.

## Decisión

Next.js App Router con `output: 'export'` — build 100% estático, sin
servidor Next.js en producción. Autenticación y toda mutación de datos
ocurre client-side contra la API. Esto:

- Elimina la dependencia de Cloudflare Pages Functions / Edge Runtime.
- Simplifica el deploy a "subir archivos estáticos" (lo que ya cubre la capa
  free de Cloudflare Pages sin configuración adicional).
- Cuesta: no hay SSR/SSG con datos dinámicos por request ni Server Actions;
  aceptable porque el dashboard familiar no tiene requisitos de SEO ni de
  first-paint con datos ya hidratados desde servidor.

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── (auth)/login/page.tsx
│   │   ├── (auth)/register/page.tsx
│   │   ├── (app)/layout.tsx            # guard de sesión, provee AuthContext
│   │   ├── (app)/dashboard/page.tsx
│   │   ├── (app)/obligations/page.tsx
│   │   ├── (app)/obligations/detail/page.tsx   # ?id=, no [id] — ver Consecuencias
│   │   ├── (app)/payments/page.tsx
│   │   └── (app)/settings/groups/page.tsx
│   ├── components/                     # UI reutilizable (Button, Card, Table...)
│   ├── features/
│   │   ├── auth/ (hooks, api.ts)
│   │   ├── obligations/ (hooks, api.ts, types.ts)
│   │   ├── payments/
│   │   └── dashboard/
│   ├── lib/
│   │   ├── api-client.ts               # fetch tipado + interceptor de refresh (ADR-001)
│   │   └── auth-context.tsx            # access token en memoria (useState/useReducer)
│   └── styles/
├── tests/                              # Vitest + Testing Library
├── next.config.ts                      # output: 'export'
└── package.json
```

## Consecuencias

- `middleware.ts` de Next.js (que requiere Edge runtime) no se usa para
  proteger rutas; el guard de sesión es un componente cliente en
  `(app)/layout.tsx` que redirige si no hay sesión válida — protección real
  sigue viviendo en el backend (todo endpoint exige JWT), esto es solo UX.
- Si en V2 se necesita SSR real (ej. SEO para una landing pública), se aísla
  en una ruta o subdominio aparte, no se revierte esta decisión para todo el app.
- **Sin segmentos dinámicos `[id]` para registros creados en runtime**: con
  `output: 'export'`, cualquier ruta `[id]` necesita `generateStaticParams()`
  enumerando todos los valores posibles en build time — imposible para IDs
  de obligaciones/pagos/etc. que los usuarios crean después del deploy
  (`next build` falla con "Page ... is missing generateStaticParams()").
  Confirmado en la práctica: la Capa Frontend 5 (detalle de obligación) se
  implementó primero como `(app)/obligations/[id]/page.tsx` y el build real
  falló por esto exacto. Patrón a seguir en su lugar para cualquier página de
  detalle de un registro: una ruta estática (ej. `(app)/obligations/detail/page.tsx`)
  que lee el id desde un query param (`?id=123`) con `useSearchParams()` en
  vez de `useParams()` — la página sigue siendo un único HTML estático, el id
  real se resuelve en el cliente después de hidratar, igual que ya hace toda
  la carga de datos de esta app.
