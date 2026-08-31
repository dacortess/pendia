"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api-client";

export default function RegisterPage() {
  const router = useRouter();
  const { register, status } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const isLoading = status === "loading";

  function validate(): boolean {
    const errors: Record<string, string> = {};

    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = "Ingresa un email válido.";
    }
    if (password.length < 8) {
      errors.password = "La contraseña debe tener al menos 8 caracteres.";
    }
    if (!fullName.trim()) {
      errors.fullName = "El nombre es obligatorio.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});

    if (!validate()) {
      return;
    }

    try {
      await register({
        email,
        password,
        full_name: fullName.trim(),
        ...(phoneNumber ? { phone_number: phoneNumber } : {}),
        ...(inviteCode ? { invite_code: inviteCode } : {}),
      });
      router.replace("/");
    } catch (err) {
      if (err instanceof ApiError) {
        switch (err.code) {
          case "EMAIL_ALREADY_EXISTS":
            setError("Ya existe una cuenta con ese email.");
            break;
          case "INVALID_INVITE_CODE":
            setError("El código de invitación no es válido o expiró.");
            break;
          case "ALREADY_MEMBER":
            setError("Ya eres miembro de ese grupo.");
            break;
          default:
            setError("No se pudo completar el registro. Intenta de nuevo.");
        }
      } else {
        setError("No se pudo completar el registro. Intenta de nuevo.");
      }
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <div>
        <label
          htmlFor="fullName"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Nombre completo
        </label>
        <input
          id="fullName"
          type="text"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
        />
        {fieldErrors.fullName && (
          <p className="text-red-600 text-xs mt-1">{fieldErrors.fullName}</p>
        )}
      </div>
      <div>
        <label
          htmlFor="email"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Email
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
        />
        {fieldErrors.email && (
          <p className="text-red-600 text-xs mt-1">{fieldErrors.email}</p>
        )}
      </div>
      <div>
        <label
          htmlFor="password"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Contraseña
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={8}
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
        />
        {fieldErrors.password && (
          <p className="text-red-600 text-xs mt-1">{fieldErrors.password}</p>
        )}
      </div>
      <div>
        <label
          htmlFor="phoneNumber"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Teléfono (opcional)
        </label>
        <input
          id="phoneNumber"
          type="tel"
          value={phoneNumber}
          onChange={(e) => setPhoneNumber(e.target.value)}
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label
          htmlFor="inviteCode"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Código de invitación (opcional)
        </label>
        <input
          id="inviteCode"
          type="text"
          value={inviteCode}
          onChange={(e) => setInviteCode(e.target.value)}
          className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
        />
        <p className="text-gray-400 text-xs mt-1">
          Si tienes un código de invitación de tu grupo familiar, ingrésalo aquí
        </p>
      </div>
      {error && (
        <div className="p-3 bg-red-50 text-red-700 rounded text-sm">
          {error}
        </div>
      )}
      <button
        type="submit"
        disabled={isLoading}
        className="w-full bg-blue-600 text-white rounded py-2 text-sm hover:bg-blue-700 disabled:opacity-50"
      >
        {isLoading
          ? "Conectando... esto puede tardar hasta un minuto la primera vez"
          : "Crear cuenta"}
      </button>
      <p className="text-center text-sm text-gray-500">
        ¿Ya tienes cuenta?{" "}
        <Link href="/login" className="text-blue-600 hover:underline">
          Inicia sesión
        </Link>
      </p>
    </form>
  );
}
