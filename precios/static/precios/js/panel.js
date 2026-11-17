async function cargarPanel() {
    const contenedor = document.getElementById("productos-tienda");
    const token = localStorage.getItem("token_comercio");

    function volverAlAcceso() {
        localStorage.removeItem("token_comercio");
        localStorage.removeItem("tienda_comercio");
        window.location.replace("/acceso/");
    }

    if (!token) {
        volverAlAcceso();
        return;
    }

    const headers = {
        Authorization: `Token ${token}`,
        Accept: "application/json"
    };

    const cerrarSesion = document.getElementById("cerrar-sesion");

    cerrarSesion.addEventListener("click", async () => {
        cerrarSesion.disabled = true;

        try {
            const respuesta = await fetch("/api/auth/logout/", {
                method: "POST",
                headers
            });

            if (!respuesta.ok && respuesta.status !== 401) {
                throw new Error("No se pudo cerrar sesión. Intentá de nuevo.");
            }

            volverAlAcceso();
        } catch (error) {
            window.alert(error.message);
            cerrarSesion.disabled = false;
        }
    });
    contenedor.textContent = "Cargando productos...";

    try {
        const [respuestaTienda, respuestaProductos] = await Promise.all([
            fetch("/api/mi-tienda/", { headers }),
            fetch("/api/mi-tienda/productos/", { headers })
        ]);

        if (respuestaTienda.status === 401 || respuestaProductos.status === 401) {
            volverAlAcceso();
            return;
        }

        if (!respuestaTienda.ok || !respuestaProductos.ok) {
            throw new Error("No se pudo cargar la información de tu tienda.");
        }

        const tienda = await respuestaTienda.json();
        document.getElementById("nombre-tienda").textContent = tienda.nombre;

        const datos = await respuestaProductos.json();
        const productos = Array.isArray(datos) ? datos : datos.results;

        if (productos.length === 0) {
            contenedor.textContent = "Tu tienda aún no tiene productos.";
            return;
        }

        const lista = document.createElement("ul");
        lista.className = "list-group";

        for (const producto of productos) {
            const fila = document.createElement("li");
            fila.className = "list-group-item";

            const nombre = document.createElement("strong");
            nombre.textContent = producto.nombre;

            const formulario = document.createElement("form");
            formulario.className = "d-flex flex-wrap gap-2 align-items-center mt-2";

            const etiqueta = document.createElement("label");
            etiqueta.htmlFor = `precio-${producto.id}`;
            etiqueta.textContent = "Precio (Bs)";

            const campo = document.createElement("input");
            campo.id = etiqueta.htmlFor;
            campo.type = "text";
            campo.inputMode = "decimal";
            campo.className = "form-control form-control-sm w-auto";
            campo.size = 10;
            campo.value = producto.precio;

            const boton = document.createElement("button");
            boton.type = "submit";
            boton.className = "btn btn-sm btn-outline-success";
            boton.textContent = "Guardar";

            const mensaje = document.createElement("span");
            mensaje.setAttribute("role", "status");

            formulario.addEventListener("submit", async (evento) => {
                evento.preventDefault();

                const precio = campo.value.trim().replace(",", ".");
                if (!/^\d{1,8}(\.\d{1,2})?$/.test(precio) || Number(precio) <= 0) {
                    mensaje.textContent = "Ingresá un precio mayor a cero, con hasta dos decimales.";
                    return;
                }

                boton.disabled = true;
                campo.disabled = true;
                mensaje.textContent = "Guardando...";

                try {
                    const respuesta = await fetch(`/api/mi-tienda/productos/${producto.id}/`, {
                        method: "PATCH",
                        headers: { ...headers, "Content-Type": "application/json" },
                        body: JSON.stringify({ precio })
                    });

                    if (respuesta.status === 401) {
                        volverAlAcceso();
                        return;
                    }

                    if (!respuesta.ok) {
                        throw new Error(`No se pudo guardar el precio (${respuesta.status}).`);
                    }

                    const actualizado = await respuesta.json();
                    campo.value = actualizado.precio;
                    mensaje.textContent = "Precio guardado.";
                } catch (error) {
                    mensaje.textContent = error.message;
                } finally {
                    boton.disabled = false;
                    campo.disabled = false;
                }
            });

            formulario.append(etiqueta, campo, boton, mensaje);
            fila.append(nombre, formulario);
            lista.appendChild(fila);
        }

        contenedor.replaceChildren(lista);
    } catch (error) {
        contenedor.textContent = error.message;
    }
}

cargarPanel();
const formularioProducto = document.getElementById("form-producto");
const botonAgregar = document.getElementById("agregar-producto");
const mensajeProducto = document.getElementById("mensaje-producto");

// Mostrar la confirmación después de recargar el panel.
const confirmacion = sessionStorage.getItem("producto-guardado");

if (confirmacion) {
    mensajeProducto.textContent = confirmacion;
    mensajeProducto.className = "text-success mt-3";
    sessionStorage.removeItem("producto-guardado");
}

botonAgregar.disabled = false;

formularioProducto.addEventListener("submit", async (evento) => {
    evento.preventDefault();

    const nombre = document.getElementById("producto-nombre").value.trim();
    const marca = document.getElementById("producto-marca").value.trim();
    const presentacion = document.getElementById("producto-presentacion").value.trim();
    const precio = document.getElementById("producto-precio").value;

    if (!nombre || !presentacion) {
        mensajeProducto.textContent = "Completá el nombre y la presentación.";
        mensajeProducto.className = "text-danger mt-3";
        return;
    }

    const token = localStorage.getItem("token_comercio");

    if (!token) {
        window.location.replace("/acceso/");
        return;
    }

    botonAgregar.disabled = true;
    botonAgregar.textContent = "Guardando...";
    mensajeProducto.textContent = "";

    try {
        const respuesta = await fetch("/api/mi-tienda/productos/", {
            method: "POST",
            headers: {
                Authorization: `Token ${token}`,
                "Content-Type": "application/json",
                Accept: "application/json"
            },
            body: JSON.stringify({
                nombre,
                marca,
                presentacion,
                precio,
                disponible: true
            })
        });

        if (respuesta.status === 401) {
            localStorage.removeItem("token_comercio");
            localStorage.removeItem("tienda_comercio");
            window.location.replace("/acceso/");
            return;
        }

        if (!respuesta.ok) {
            const errores = await respuesta.json().catch(() => null);
            throw new Error(
                errores
                    ? JSON.stringify(errores)
                    : `No se pudo guardar (${respuesta.status}).`
            );
        }

        const producto = await respuesta.json();

        sessionStorage.setItem(
            "producto-guardado",
            `${producto.nombre}: precio publicado correctamente.`
        );

        window.location.reload();
    } catch (error) {
        mensajeProducto.textContent = error.message;
        mensajeProducto.className = "text-danger mt-3";
    } finally {
        botonAgregar.disabled = false;
        botonAgregar.textContent = "Agregar producto";
    }
});