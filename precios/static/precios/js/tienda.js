async function cargarTienda() {
    const pagina = document.getElementById("detalle-tienda");
    const mensaje = document.getElementById("mensaje-tienda");
    const promociones = document.getElementById("tienda-promociones");
    const productos = document.getElementById("tienda-productos");
    const slug = pagina.dataset.slug;

    function moneda(valor) {
        return "Bs " + Number(valor).toLocaleString("es-BO", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function tarjeta(titulo, detalle, precio, nota) {
        const columna = document.createElement("div");
        columna.className = "col-md-6 col-lg-4";

        const articulo = document.createElement("article");
        articulo.className = "card h-100 shadow-sm";

        const cuerpo = document.createElement("div");
        cuerpo.className = "card-body";

        const encabezado = document.createElement("h3");
        encabezado.className = "h5";
        encabezado.textContent = titulo;

        const descripcion = document.createElement("p");
        descripcion.className = "text-secondary";
        descripcion.textContent = detalle;

        const importe = document.createElement("p");
        importe.className = "h5 text-success";
        importe.textContent = precio;

        const pie = document.createElement("small");
        pie.className = "text-secondary";
        pie.textContent = nota;

        cuerpo.append(encabezado, descripcion, importe, pie);
        articulo.appendChild(cuerpo);
        columna.appendChild(articulo);

        return columna;
    }

    async function consultar(url) {
        const respuesta = await fetch(url);

        if (!respuesta.ok) {
            throw new Error(
                respuesta.status === 404
                    ? "La tienda no existe o no está activa."
                    : "No se pudo cargar la tienda."
            );
        }

        return respuesta.json();
    }

    try {
        const ruta = "/api/tiendas/" + encodeURIComponent(slug) + "/";

        const [tienda, catalogo] = await Promise.all([
            consultar(ruta),
            consultar(ruta + "productos/")
        ]);

        document.title = tienda.nombre + " | ComparaPrecios";
        document.getElementById("tienda-nombre").textContent = tienda.nombre;
        document.getElementById("tienda-descripcion").textContent =
            tienda.descripcion || "";
        document.getElementById("tienda-direccion").textContent =
            "Dirección: " + (tienda.direccion || "No registrada") +
            (tienda.zona ? " · " + tienda.zona : "");
        document.getElementById("tienda-horarios").textContent =
            "Horarios: " + (tienda.horarios || "Consultar al comercio");

        promociones.replaceChildren();

        for (const promocion of tienda.promociones || []) {
            const vigencia = promocion.valida_hasta
                ? "Válida hasta: " + promocion.valida_hasta
                : "Sin fecha de finalización publicada";

            promociones.appendChild(
                tarjeta(
                    promocion.titulo,
                    promocion.descripcion || "",
                    promocion.precio_promo != null
                        ? moneda(promocion.precio_promo)
                        : "Consultar promoción",
                    vigencia
                )
            );
        }

        if (!promociones.children.length) {
            promociones.textContent = "Esta tienda no tiene promociones vigentes.";
        }

        productos.replaceChildren();

        for (const producto of catalogo) {
            const detalle = [
                producto.marca,
                producto.presentacion,
                producto.categoria
            ].filter(Boolean).join(" · ");

            const fecha = producto.actualizado
                ? new Date(producto.actualizado).toLocaleDateString("es-BO")
                : "Sin fecha";

            productos.appendChild(
                tarjeta(
                    producto.nombre,
                    detalle,
                    moneda(producto.precio_efectivo),
                    "Actualizado: " + fecha
                )
            );
        }

        if (!productos.children.length) {
            productos.textContent = "No hay productos disponibles publicados.";
        }

        mensaje.textContent = "";
    } catch (error) {
        mensaje.className = "alert alert-danger";
        mensaje.textContent = error.message;
    }
}

cargarTienda();
