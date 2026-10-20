############################################################
# Presupuesto mensual con alertas (opcional). No limita el gasto: solo avisa por correo.
# Se crea únicamente si budget_amount > 0 y hay al menos un correo.
############################################################

resource "azurerm_consumption_budget_resource_group" "monthly" {
  count = var.budget_amount > 0 && length(var.budget_alert_emails) > 0 && local.has_resource_group ? 1 : 0

  name              = "presupuesto-framework-sql"
  resource_group_id = local.support_resource_group_id

  amount     = var.budget_amount
  time_grain = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = var.budget_alert_emails
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_emails = var.budget_alert_emails
  }
}
