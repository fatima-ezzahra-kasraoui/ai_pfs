import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";
import { useAuth } from "../auth/AuthContext";

export const loginSchema = z.object({
  username: z.string().trim().min(1, "Identifiant requis"),
  password: z.string().min(1, "Mot de passe requis"),
});
type LoginForm = z.infer<typeof loginSchema>;

/** N'accepte qu'un chemin interne : évite une redirection ouverte (`//autre-site`, `https://…`). */
export function safeRedirect(target: unknown): string {
  return typeof target === "string" && /^\/(?![/\\])/.test(target) ? target : "/";
}

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [failed, setFailed] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  const destination = safeRedirect((location.state as { from?: string } | null)?.from);
  if (user) return <Navigate to={destination} replace />;

  const onSubmit = async (values: LoginForm) => {
    setFailed(false);
    try {
      await login(values.username, values.password);
      navigate(destination, { replace: true });
    } catch {
      // Message volontairement générique : ne révèle ni l'existence du compte ni la cause de l'échec.
      setFailed(true);
    }
  };

  return (
    <main className="login">
      <h1>Connexion</h1>
      <form onSubmit={handleSubmit(onSubmit)} noValidate aria-label="Connexion">
        <label htmlFor="username">Identifiant</label>
        <input id="username" autoComplete="username" aria-invalid={!!errors.username} aria-describedby={errors.username ? "username-error" : undefined} {...register("username")} />
        {errors.username && (
          <p id="username-error" role="alert" className="field-error">
            {errors.username.message}
          </p>
        )}

        <label htmlFor="password">Mot de passe</label>
        <input id="password" type="password" autoComplete="current-password" aria-invalid={!!errors.password} aria-describedby={errors.password ? "password-error" : undefined} {...register("password")} />
        {errors.password && (
          <p id="password-error" role="alert" className="field-error">
            {errors.password.message}
          </p>
        )}

        {failed && (
          <p role="alert" className="form-error">
            Identifiants invalides.
          </p>
        )}
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Connexion…" : "Se connecter"}
        </button>
      </form>
    </main>
  );
}
