package ma.agentshield.config;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

class GlobalExceptionHandlerTest {

    @RestController
    static class FakeController {
        @GetMapping("/boom")
        String boom() {
            throw new IllegalStateException("secret interne : jdbc:postgresql://db/prod");
        }

        @GetMapping("/bad-credentials")
        String badCredentials() {
            throw new BadCredentialsException("detail interne : utilisateur inconnu");
        }

        @GetMapping("/denied")
        String denied() {
            throw new AccessDeniedException("detail interne");
        }

        @GetMapping("/forbidden")
        String forbidden() {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN);
        }
    }

    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders.standaloneSetup(new FakeController())
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    void unexpectedExceptionReturnsGenericErrorWithoutInternalDetail() throws Exception {
        mvc.perform(get("/boom"))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.status").value(500))
                .andExpect(jsonPath("$.code").value("INTERNAL_ERROR"))
                .andExpect(jsonPath("$.message").value("Erreur interne."))
                .andExpect(content().string(org.hamcrest.Matchers.not(
                        org.hamcrest.Matchers.containsString("jdbc"))))
                .andExpect(content().string(org.hamcrest.Matchers.not(
                        org.hamcrest.Matchers.containsString("stackTrace"))));
    }

    @Test
    void responseStatusExceptionKeepsItsStatus() throws Exception {
        mvc.perform(get("/forbidden"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("FORBIDDEN"));
    }

    @Test
    void authenticationFailureIsAGenericInvalidCredentials401() throws Exception {
        mvc.perform(get("/bad-credentials"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("INVALID_CREDENTIALS"))
                .andExpect(jsonPath("$.message").value("Identifiants invalides."))
                .andExpect(content().string(org.hamcrest.Matchers.not(
                        org.hamcrest.Matchers.containsString("inconnu"))));
    }

    @Test
    void accessDeniedIsAGeneric403() throws Exception {
        mvc.perform(get("/denied"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("FORBIDDEN"))
                .andExpect(content().string(org.hamcrest.Matchers.not(
                        org.hamcrest.Matchers.containsString("interne"))));
    }
}
