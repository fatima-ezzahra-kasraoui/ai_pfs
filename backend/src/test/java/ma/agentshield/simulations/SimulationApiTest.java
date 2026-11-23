package ma.agentshield.simulations;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;
import static org.hamcrest.Matchers.matchesPattern;
import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.jayway.jsonpath.JsonPath;
import java.time.Duration;
import java.util.List;
import ma.agentshield.integration.AgentRunResponse;
import ma.agentshield.integration.AgentRunResponse.AgentEvent;
import ma.agentshield.integration.AiServiceClient;
import ma.agentshield.integration.AiServiceException;
import ma.agentshield.support.PostgresTestConfig;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

/**
 * AS-S1-020 : POST 202 + SUBMITTED, GET au format du contrat, scenario inconnu -> 400, service IA indisponible ->
 * FAILED. Le service IA est simule par un mock du client (contrat provisoire de /internal/agent/run).
 */
@SpringBootTest
@Import(PostgresTestConfig.class)
@AutoConfigureMockMvc
@ActiveProfiles("test")
class SimulationApiTest {

    private static final String UUID_PATTERN = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$";

    @Autowired
    private MockMvc mvc;

    @Autowired
    private SimulationRepository simulations;

    @MockitoBean
    private AiServiceClient aiClient;

    @BeforeEach
    void stubAiService() {
        simulations.deleteAll();
        when(aiClient.runAgent(argThat(r -> r != null && "unprotected".equals(r.mode())), anyString()))
                .thenReturn(new AgentRunResponse(true, null, "ALLOW", 0, 3.0, List.of()));
        when(aiClient.runAgent(argThat(r -> r != null && "protected".equals(r.mode())), anyString()))
                .thenReturn(new AgentRunResponse(false, null, "BLOCK", 0, 5.0,
                        List.of(new AgentEvent("input", "A", "BLOCK", 0.97, "jailbreak", 1.5))));
    }

    private String runScenario(String scenarioId) throws Exception {
        String json = mvc.perform(post("/api/simulations/run").with(user("analyste").roles("ANALYST"))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"scenarioId\":\"" + scenarioId + "\"}"))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.status").value("SUBMITTED"))
                .andExpect(jsonPath("$.simulationId").value(matchesPattern(UUID_PATTERN)))
                .andReturn().getResponse().getContentAsString();
        return JsonPath.read(json, "$.simulationId");
    }

    @Test
    void runReturns202ThenTheSimulationCompletesWithBothRuns() throws Exception {
        String id = runScenario("scenario-1");

        await().atMost(Duration.ofSeconds(15)).untilAsserted(() ->
                mvc.perform(get("/api/simulations/" + id).with(user("analyste").roles("ANALYST")))
                        .andExpect(status().isOk())
                        .andExpect(jsonPath("$.status").value("COMPLETED")));

        mvc.perform(get("/api/simulations/" + id).with(user("analyste").roles("ANALYST")))
                .andExpect(jsonPath("$.simulationId").value(id))
                .andExpect(jsonPath("$.scenarioId").value("scenario-1"))
                .andExpect(jsonPath("$.createdAt").isNotEmpty())
                .andExpect(jsonPath("$.completedAt").isNotEmpty())
                .andExpect(jsonPath("$.error").value(nullValue()))
                .andExpect(jsonPath("$.unprotected.mode").value("unprotected"))
                .andExpect(jsonPath("$.unprotected.attackSucceeded").value(true))
                .andExpect(jsonPath("$.protected.mode").value("protected"))
                .andExpect(jsonPath("$.protected.attackSucceeded").value(false))
                .andExpect(jsonPath("$.protected.finalDecision").value("BLOCK"))
                .andExpect(jsonPath("$.protected.steps[0].name").value("input"))
                .andExpect(jsonPath("$.protected.steps[0].status").value("DONE"))
                .andExpect(jsonPath("$.protected.steps[0].module").value("A"))
                .andExpect(jsonPath("$.protected.steps[0].decision").value("BLOCK"))
                .andExpect(jsonPath("$.protected.steps[0].score").value(0.97));
    }

    @Test
    void anUnknownScenarioIs400AndNothingIsStored() throws Exception {
        mvc.perform(post("/api/simulations/run").with(user("analyste").roles("ANALYST"))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"scenarioId\":\"scenario-99\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.code").value("BAD_REQUEST"))
                .andExpect(jsonPath("$.message").value("Scenario inconnu."));

        assertThat(simulations.count()).isZero();
        verifyNoInteractions(aiClient);
    }

    @Test
    void aMalformedScenarioIdIs400() throws Exception {
        for (String bad : List.of("../etc/passwd", "SCENARIO-1", "")) {
            mvc.perform(post("/api/simulations/run").with(user("analyste").roles("ANALYST"))
                            .contentType(MediaType.APPLICATION_JSON).content("{\"scenarioId\":\"" + bad + "\"}"))
                    .andExpect(status().isBadRequest());
        }
        verifyNoInteractions(aiClient);
    }

    @Test
    void anUnavailableAiServiceEndsInFailedWithAGenericMessage() throws Exception {
        when(aiClient.runAgent(any(), anyString())).thenThrow(new AiServiceException(new RuntimeException("jdbc://secret-interne")));

        String id = runScenario("scenario-2");

        await().atMost(Duration.ofSeconds(15)).untilAsserted(() ->
                mvc.perform(get("/api/simulations/" + id).with(user("analyste").roles("ANALYST")))
                        .andExpect(jsonPath("$.status").value("FAILED")));

        mvc.perform(get("/api/simulations/" + id).with(user("analyste").roles("ANALYST")))
                .andExpect(jsonPath("$.error").value("Service IA indisponible."))
                .andExpect(jsonPath("$.unprotected").value(nullValue()))
                .andExpect(jsonPath("$.protected").value(nullValue()))
                .andExpect(content().string(org.hamcrest.Matchers.not(
                        org.hamcrest.Matchers.containsString("secret-interne"))));
    }

    @Test
    void anApproverCannotRunASimulation() throws Exception {
        mvc.perform(post("/api/simulations/run").with(user("valideur").roles("APPROVER"))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"scenarioId\":\"scenario-1\"}"))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("FORBIDDEN"));

        assertThat(simulations.count()).isZero();
        verifyNoInteractions(aiClient);
    }

    @Test
    void anApproverCanReadASimulation() throws Exception {
        Simulation sim = simulations.save(new Simulation("scenario-1", null));

        mvc.perform(get("/api/simulations/" + sim.getId()).with(user("valideur").roles("APPROVER")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("SUBMITTED"))
                .andExpect(jsonPath("$.unprotected").value(nullValue()));
    }

    @Test
    void unknownOrInvalidIdsAre404() throws Exception {
        mvc.perform(get("/api/simulations/00000000-0000-0000-0000-000000000000").with(user("a").roles("ANALYST")))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NOT_FOUND"));
        mvc.perform(get("/api/simulations/pas-un-uuid").with(user("a").roles("ANALYST")))
                .andExpect(status().isNotFound());
    }

    @Test
    void bothEndpointsRequireASession() throws Exception {
        mvc.perform(post("/api/simulations/run").contentType(MediaType.APPLICATION_JSON).content("{\"scenarioId\":\"scenario-1\"}"))
                .andExpect(status().isUnauthorized());
        mvc.perform(get("/api/simulations/00000000-0000-0000-0000-000000000000")).andExpect(status().isUnauthorized());
    }
}
