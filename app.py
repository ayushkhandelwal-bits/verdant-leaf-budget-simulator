# Verdant Leaf - Q1 2026 budget simulator
# Uses the fitted values from new_mmm_model.py (saved in model_params.json)
# Run: streamlit run app.py

import json
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(page_title="Verdant Leaf budget simulator", layout="centered")

p = json.load(open("model_params.json"))
names = p["names"]
current = p["current_cr"]
recommended = p["recommended_cr"]
BUDGET = 16.0


def channel_revenue(i, spend_cr):
    # expected Q1 revenue (Rs Cr) from one channel, same set-up as the model:
    # 13 weeks of spend (TV as one 4-week flight) + 8 weeks for carry-over
    weekly = np.zeros(21)
    if names[i] == "TV":
        weekly[4:8] = spend_cr * 1e7 / 4
    else:
        weekly[0:13] = spend_cr * 1e7 / 13
    decay = p["decay"][i]
    a = np.zeros(21)
    for w in range(21):
        a[w] = weekly[w] + (decay * a[w - 1] if w > 0 else 0)
    a = a * (1 - decay)
    effect = a / (a + p["half_sat"][i])
    return p["coef_avg"][i] * effect.sum() / 1e7


def total_revenue(spends):
    return sum(channel_revenue(i, s) for i, s in enumerate(spends))


# ---------- presets ----------
def set_mix(mix):
    for i, n in enumerate(names):
        st.session_state[n] = round(mix[i], 2)


if names[0] not in st.session_state:
    set_mix(recommended)

st.title("Verdant Leaf: Q1 2026 budget simulator")
st.caption("Move the sliders to split ₹16 Cr. Each channel stays within 50–150% of its 2025 average quarter.")

c1, c2 = st.columns(2)
c1.button("Last year's mix", on_click=set_mix, args=(current,), width="stretch")
c2.button("Recommended mix", on_click=set_mix, args=(recommended,), width="stretch")

# ---------- sliders ----------
spends = []
for i, n in enumerate(names):
    lo, hi = round(current[i] * 0.5, 2), round(current[i] * 1.5, 2)
    spends.append(st.slider(f"{n} (₹ Cr)", min_value=lo, max_value=hi, step=0.01, key=n))

total_spend = sum(spends)
revenue = total_revenue(spends)
base = total_revenue(current)

# ---------- results ----------
st.divider()
m1, m2, m3 = st.columns(3)
on_budget = abs(total_spend - BUDGET) <= 0.015     # allow for rounding to 2 decimals
gain = revenue - base
if on_budget:
    m1.metric("Budget used (on budget)", f"₹{total_spend:.1f} Cr")
else:
    m1.metric("Budget used", f"₹{total_spend:.2f} Cr", f"{total_spend - BUDGET:+.2f} vs ₹16 Cr", delta_color="off")
m2.metric("Expected Q1 revenue from ads", f"₹{revenue:.1f} Cr")
m3.metric("vs last year's mix", "no change" if abs(gain) < 0.005 else f"{gain:+.1f} Cr")

if not on_budget:
    st.warning(f"The split adds up to ₹{total_spend:.2f} Cr. Adjust it to ₹16.00 Cr to compare fairly.")

# ---------- where the next rupee works hardest ----------
st.subheader("What the next ₹10 lakh would bring")
rows = []
for i, n in enumerate(names):
    extra = channel_revenue(i, spends[i] + 0.1) - channel_revenue(i, spends[i])
    rows.append({"Channel": n, "Spend (₹ Cr)": round(spends[i], 2),
                 "Revenue (₹ Cr)": round(channel_revenue(i, spends[i]), 2),
                 "Next ₹10 lakh → revenue (₹ lakh)": round(extra * 100, 1)})
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

# ---------- diminishing returns for one channel ----------
st.subheader("Diminishing returns")
pick = st.selectbox("Channel", names, index=2)
i = names.index(pick)
xs = np.linspace(current[i] * 0.5, current[i] * 1.5, 40)
curve = pd.DataFrame({"Spend (₹ Cr)": xs, "Revenue (₹ Cr)": [channel_revenue(i, x) for x in xs]})
now = pd.DataFrame({"Spend (₹ Cr)": [spends[i]], "Revenue (₹ Cr)": [channel_revenue(i, spends[i])]})
chart = (alt.Chart(curve).mark_line().encode(x="Spend (₹ Cr)", y="Revenue (₹ Cr)")
         + alt.Chart(now).mark_point(size=120, filled=True, color="#E07A5F").encode(x="Spend (₹ Cr)", y="Revenue (₹ Cr)"))
st.altair_chart(chart, width="stretch")
st.caption(f"{pick}: 2025 return ₹{p['roi_2025'][i]:.2f} per ₹1 (likely range {p['roi_low'][i]:.1f}–{p['roi_high'][i]:.1f}).")

st.info("Revenue figures are averages over 300 bootstrap refits of the model, so they match the report. "
        "The recommended mix was optimised on the best-fit model, where Google's return is 0. "
        "In some refits Google comes out positive, so here it looks a bit better at the margin: "
        "it is the least certain channel (0–4), and a brand-search holdout test would settle it.")
