document.addEventListener("DOMContentLoaded", function () {
    const formulario = document.getElementById("login-form");

    formulario.addEventListener("submit", iniciarSesion);
});


async function iniciarSesion(evento) {
    evento.preventDefault();

    const usuario = document.getElementById("login-usuario").value.trim();
    const clave = document.getElementById("login-clave").value;
    const boton = document.getElementById("login-boton");
    const mensaje = document.getElementById("login-mensaje");

    mensaje.className = "alert d-none";
    boton.disabled = true;
    boton.textContent = "Ingresando...";

    try {
        const respuesta = await fetch("/api/auth/login/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                username: usuario,
                password: clave
            })
        });

        const datos = await respuesta.json();

        if (!respuesta.ok) {
            throw new Error(
                datos.detail || "No se pudo iniciar sesión."
            );
        }

        localStorage.setItem("token_comercio", datos.token);
        localStorage.setItem(
            "tienda_comercio",
            JSON.stringify(datos.tienda)
        );

        window.location.href = "/panel/";

    } catch (error) {
        mensaje.textContent = error.message;
        mensaje.className = "alert alert-danger";

    } finally {
        boton.disabled = false;
        boton.textContent = "Ingresar";
    }
}