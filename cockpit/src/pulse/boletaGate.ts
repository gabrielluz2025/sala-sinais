import type { ExecutionStatusRead, SystemState } from "../api/client";

export function applyBoletaExecutionGate(
  state: SystemState | null,
  exec: ExecutionStatusRead | null,
): void {
  const buy = document.getElementById("boleta-buy") as HTMLButtonElement | null;
  const sell = document.getElementById("boleta-sell") as HTMLButtonElement | null;
  if (!buy || !sell) return;

  let disabled = false;
  let tip = "";

  if (state?.engine_paused) {
    disabled = true;
    tip = "Motor pausado — clique Retomar no menu esquerdo para comprar/vender";
  } else if (exec?.operating_mode === "live_mt5" && !exec.can_execute && !exec.can_send_orders) {
    disabled = true;
    tip = exec.blockers.length ? exec.blockers.join(" · ") : "Execução live bloqueada pela política";
  }

  for (const btn of [buy, sell]) {
    btn.disabled = disabled;
    if (disabled && tip) {
      btn.title = tip;
    } else {
      btn.removeAttribute("title");
    }
  }
}
