############################################################
# VM NUEVA (modo excepcional, desactivado por defecto)
# Solo existe si create_new_vm = true, use_existing_vm = false y confirm_create_new_vm = "CREATE-NEW-VM".
# Con la configuración por defecto, `terraform plan` NO contiene ninguno de estos recursos.
# Sirve para reproducir el entorno desde cero (p. ej. en otra suscripción), no para tocar la VM actual.
############################################################

locals {
  new_vm_enabled = var.create_new_vm
}

resource "azurerm_resource_group" "new" {
  count    = local.new_vm_enabled ? 1 : 0
  name     = var.new_vm_resource_group_name
  location = var.new_vm_location
  tags     = var.tags
}

resource "azurerm_virtual_network" "new" {
  count               = local.new_vm_enabled ? 1 : 0
  name                = "vnet-framework-sql"
  address_space       = ["10.20.0.0/16"]
  location            = azurerm_resource_group.new[0].location
  resource_group_name = azurerm_resource_group.new[0].name
  tags                = var.tags
}

resource "azurerm_subnet" "new" {
  count                = local.new_vm_enabled ? 1 : 0
  name                 = "snet-app"
  resource_group_name  = azurerm_resource_group.new[0].name
  virtual_network_name = azurerm_virtual_network.new[0].name
  address_prefixes     = ["10.20.1.0/24"]
}

resource "azurerm_public_ip" "new" {
  count               = local.new_vm_enabled ? 1 : 0
  name                = "pip-framework-sql"
  location            = azurerm_resource_group.new[0].location
  resource_group_name = azurerm_resource_group.new[0].name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = var.new_vm_domain_name_label != "" ? var.new_vm_domain_name_label : null
  tags                = var.tags
}

resource "azurerm_network_security_group" "new" {
  count               = local.new_vm_enabled ? 1 : 0
  name                = "nsg-framework-sql"
  location            = azurerm_resource_group.new[0].location
  resource_group_name = azurerm_resource_group.new[0].name
  tags                = var.tags

  security_rule {
    name                       = "web-http"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "web-https"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # SSH solo desde los CIDR indicados; el puerto 1521 de Oracle NO se publica nunca.
  dynamic "security_rule" {
    for_each = length(var.new_vm_ssh_allowed_cidrs) > 0 ? [1] : []
    content {
      name                       = "ssh-restringido"
      priority                   = 200
      direction                  = "Inbound"
      access                     = "Allow"
      protocol                   = "Tcp"
      source_port_range          = "*"
      destination_port_range     = "22"
      source_address_prefixes    = var.new_vm_ssh_allowed_cidrs
      destination_address_prefix = "*"
    }
  }
}

resource "azurerm_subnet_network_security_group_association" "new" {
  count                     = local.new_vm_enabled ? 1 : 0
  subnet_id                 = azurerm_subnet.new[0].id
  network_security_group_id = azurerm_network_security_group.new[0].id
}

resource "azurerm_network_interface" "new" {
  count               = local.new_vm_enabled ? 1 : 0
  name                = "nic-framework-sql"
  location            = azurerm_resource_group.new[0].location
  resource_group_name = azurerm_resource_group.new[0].name
  tags                = var.tags

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.new[0].id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.new[0].id
  }
}

resource "azurerm_linux_virtual_machine" "new" {
  count               = local.new_vm_enabled ? 1 : 0
  name                = "vm-framework-sql"
  resource_group_name = azurerm_resource_group.new[0].name
  location            = azurerm_resource_group.new[0].location
  size                = var.new_vm_size
  admin_username      = var.new_vm_admin_username
  tags                = var.tags

  network_interface_ids           = [azurerm_network_interface.new[0].id]
  disable_password_authentication = true

  admin_ssh_key {
    username   = var.new_vm_admin_username
    public_key = var.new_vm_ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
    disk_size_gb         = var.new_vm_os_disk_gb
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }

  # Instala Docker y deja las carpetas de la aplicación; el despliegue lo hace el workflow deploy.yml.
  custom_data = base64encode(file("${path.module}/cloud-init.yaml"))

  lifecycle {
    # Una VM creada por Terraform no debe destruirse ni reemplazarse por un cambio de imagen.
    prevent_destroy = true
    ignore_changes  = [source_image_reference, custom_data]
  }
}
