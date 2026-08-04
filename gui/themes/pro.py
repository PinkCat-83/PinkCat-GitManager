"""
themes/pro.py
Tema profesional (fondo claro), derivado de PinkCat AutoCalendar.
Sin variante oscura — si se necesita en el futuro, sería un tema nuevo
(theme_pro_dark), no una opción dentro de este.

Los valores de success/danger/warning/info son propios de este tema
(no coinciden con themes/green.py ni themes/pink.py): al ser un fondo
claro, los tonos saturados pensados para fondo oscuro no dan contraste
suficiente. Se mantiene la misma familia de color (rojo=error,
ámbar=aviso, verde=éxito), con hex distintos. Ver Design System §3.
"""

THEME = {
    "bg":          "#EBEBEB",
    "panel":       "#DDE4ED",
    "card":        "#FFFFFF",
    "card_hover":  "#F0F4F8",
    "border":      "#BDBDBD",

    "accent":      "#2E86C1",
    "accent_dim":  "#1F6690",

    "success":     "#27AE60",
    "danger":      "#C0392B",
    "warning":     "#E67E22",
    "info":        "#1A3A5C",

    "text":        "#1a1a1a",
    "text_dim":    "#808080",
    "text_muted":  "#F0F0F0",

    "corner_radius_card": 8,
    "corner_radius_btn":  6,
}
