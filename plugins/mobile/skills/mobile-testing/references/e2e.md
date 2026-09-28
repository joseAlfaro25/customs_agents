# E2E con Maestro y Detox

Léelo al crear o mantener tests end-to-end, o al decidir qué herramienta usar.

## Cuál elegir
| Criterio | Maestro | Detox |
|---|---|---|
| Setup | Binario + YAML, sin tocar código nativo | Paquete npm + config nativa (prebuild, config plugin) |
| Estilo | Black-box, tolerante a esperas | Grey-box, sincroniza con el bridge/animaciones |
| Lenguaje | YAML (+ JS opcional) | JS/TS con Jest |
| CI | Maestro Cloud, EAS Workflows, runners propios | Runners macOS/Linux con emuladores propios |
| Ideal para | Smoke tests y flujos críticos, equipos pequeños | Suites grandes con lógica y mocks |

Recomendación por defecto en proyectos Expo: **Maestro**, salvo que el proyecto ya tenga Detox.

## testIDs
- Añade `testID` estables solo a elementos que el e2e necesita y no se localizan bien por texto o label.
- Naming: `feature.element` en `kebab-case` (`login.submit-button`, `orders.list`).
- No cambies textos visibles solo para tests; prefiere `testID` o labels de accesibilidad.

## Maestro
Instalación (máquina local): sigue la guía oficial de maestro.dev (script de instalación o Homebrew). Requiere Java en algunas plataformas.

```yaml
# .maestro/login.yaml
appId: com.example.app            # bundleIdentifier / package de app.json
---
- launchApp:
    clearState: true
- tapOn:
    id: "login.email-input"
- inputText: "qa@example.com"
- tapOn:
    id: "login.password-input"
- inputText: ${PASSWORD}
- hideKeyboard
- tapOn: "Entrar"
- assertVisible: "Pedidos"
- takeScreenshot: login-success
```
```yaml
# .maestro/deeplink-order.yaml
appId: com.example.app
---
- launchApp
- openLink: myapp://orders/123
- assertVisible:
    id: "order-detail.title"
```
- Ejecutar: `maestro test .maestro/` (con un simulador/emulador corriendo y la app instalada).
- Variables: `maestro test -e PASSWORD=... .maestro/login.yaml`. No subas credenciales reales al repo.
- Reutiliza pasos con `runFlow: common/login.yaml`.
- `maestro studio` ayuda a descubrir selectores.
- Usa un build tipo release/preview (no Expo Go). En EAS, un perfil con `ios.simulator: true` y APK para Android facilita instalar en simuladores.
- EAS Workflows tiene soporte para ejecutar flujos Maestro en CI (ver `expo:eas-workflows` si está instalado, o la doc de EAS).

## Detox
Pasos generales para Expo (verifica en la doc actual de Detox y del config plugin):
1. `npm i -D detox` y el config plugin de la comunidad para Detox (`@config-plugins/detox`), añadido a `plugins` en app config.
2. `npx expo prebuild` (Detox necesita los proyectos nativos).
3. `.detoxrc.js` con configuraciones `ios.sim.release` / `android.emu.release` apuntando al binario generado.
4. `detox build -c ios.sim.release` y `detox test -c ios.sim.release`.

```ts
// e2e/login.test.ts
describe('Login', () => {
  beforeAll(async () => {
    await device.launchApp({ newInstance: true, delete: true });
  });

  it('inicia sesión y ve pedidos', async () => {
    await element(by.id('login.email-input')).typeText('qa@example.com');
    await element(by.id('login.password-input')).typeText(process.env.E2E_PASSWORD!);
    await element(by.id('login.submit-button')).tap();
    await expect(element(by.text('Pedidos'))).toBeVisible();
  });
});
```
- Animaciones infinitas o timers largos bloquean la sincronización de Detox: desactívalos en modo e2e o usa `device.disableSynchronization()` puntualmente.

## Datos y entorno
- Backend de staging/QA dedicado o mocks a nivel de red; nunca producción.
- Usuarios de prueba con datos deterministas y reseteables.
- `EXPO_PUBLIC_API_URL` del build e2e apuntando al entorno de QA (perfil de EAS o `.env` específico).

## Flujos mínimos recomendados
1. Arranque en frío hasta la primera pantalla.
2. Login correcto y erróneo.
3. Flujo de negocio principal (crear pedido, pagar, etc.).
4. Deep link a una pantalla interna (con y sin sesión).
5. Logout.

## Flakiness
- Espera por elementos (`assertVisible`, `waitFor`), nunca `sleep` fijo salvo último recurso.
- `clearState` / `delete: true` entre flujos que dependen de estado limpio.
- Desactiva animaciones del sistema en emuladores de CI.
- Captura screenshots/videos en fallos para depurar.
